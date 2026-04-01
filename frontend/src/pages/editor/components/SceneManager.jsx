
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
export const ReferenceManager = ({ shot, entities, onUpdate, title = "Reference Images", promptText = "", onPickMedia = null, useSequenceLogic = false, storageKey = "ref_image_urls", additionalAutoRefs = [], strictPromptOnly = false, onFindPrevFrame = null, uiLang = 'zh' }) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [selectedImage, setSelectedImage] = useState(null);
    const tech = JSON.parse(shot.technical_notes || '{}');
    const isVideoRefManager = storageKey === 'video_ref_image_urls';
    const resolvedVideoMode = resolveUnifiedVideoMode(tech);
    const isVideoManualOverride = isVideoRefManager && tech.video_ref_image_urls_manual === true;

    const getEntityMatches = () => collectMatchedEntitiesFromPrompt({
        promptText,
        associatedEntities: shot?.associated_entities || '',
        entityPool: entities,
        includeAssociatedEntities: !strictPromptOnly,
    });

    const getVideoPromptEntityRefs = () => collectMatchedSubjectImageUrlsFromPrompt({
        promptText,
        entityPool: entities,
    });

    useEffect(() => {
        if (useSequenceLogic || !isVideoRefManager || isVideoManualOverride) return;

        const seededRefs = buildAutoVideoRefList(shot, tech, resolvedVideoMode, getVideoPromptEntityRefs());
        const existingRefs = normalizeMediaRefList(tech[storageKey]);
        if (areMediaRefListsEqual(existingRefs, seededRefs)) return;

        const seededTech = {
            ...tech,
            [storageKey]: seededRefs,
            video_ref_image_urls_manual: false,
            [`${storageKey}_user_edited`]: false,
        };
        onUpdate({ technical_notes: JSON.stringify(seededTech) });
    }, [useSequenceLogic, isVideoRefManager, isVideoManualOverride, tech, storageKey, shot, resolvedVideoMode, onUpdate, promptText, entities, strictPromptOnly]);

    let activeRefs = [];
    
    // Normal Mode vs Sequence Mode
    if (useSequenceLogic) {
        // Force Order: [Start Frame, ...Keyframes, End Frame]
        if (shot.image_url) activeRefs.push(shot.image_url);
        if (tech.keyframes && Array.isArray(tech.keyframes)) {
            activeRefs.push(...tech.keyframes);
        }
        if (tech.end_frame_url) activeRefs.push(tech.end_frame_url);
        // Deduplicate while preserving order if needed, but for sequence, duplicates might differ by position technically
        // but image url same means same image. Let's uniq by URL to avoid UI keys issues
        activeRefs = [...new Set(activeRefs)];
    } else if (isVideoRefManager) {
        // WYSIWYG: submit/render should use the exact refs currently stored for video mode.
        // Auto-build is only a fallback when no stored list exists yet.
        if (Array.isArray(tech[storageKey])) {
            activeRefs = normalizeMediaRefList(tech[storageKey]);
        } else {
            activeRefs = buildAutoVideoRefList(shot, tech, resolvedVideoMode, getVideoPromptEntityRefs());
        }
    } else {
        // Standard entity/manual ref logic
        const isManualMode = tech[storageKey] && Array.isArray(tech[storageKey]);
           const userEditedKey = `${storageKey}_user_edited`;
           const isUserEdited = Boolean(tech[userEditedKey]);
           const isLockedManual = isManualMode && isUserEdited;
        
        const shouldDetectEntities = storageKey !== 'video_ref_image_urls';
        const matchedEntities = shouldDetectEntities ? getEntityMatches() : [];
        const autoMatches = matchedEntities.map(e => e.image_url).filter(Boolean);
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
               // 用户已手动调整后：完全以用户列表为准，不再自动匹配/注入
               activeRefs = [...tech[storageKey]];
           } else if (isManualMode) {
                         // Manual but not locked: treat stored list as cache only.
                         // Recompute from current subject/entity latest images each reload.
                         activeRefs = [...autoMatches];
        } else {
             // Auto Mode: Visualize what will be used by default (since nothing saved yet)
             activeRefs = [...autoMatches];

            // --- GLOBAL INJECTION RULES (Apply only in Auto Mode to allow manual overrides) ---
            
            // 1. Inject Additional Auto Refs (e.g. Previous Shot End Frame for Start Refs)
            if (additionalAutoRefs && additionalAutoRefs.length > 0) {
                // Iterate in reverse to keep order when unshifting
                for (let i = additionalAutoRefs.length - 1; i >= 0; i--) {
                    const ref = additionalAutoRefs[i];
                    if (!activeRefs.includes(ref)) {
                        activeRefs.unshift(ref);
                    }
                }
            }
        }
        
        // 2. Special Logic for End Refs: Always include Start Frame (Global Injection to ensure Realtime Updates)
        if (!isLockedManual && storageKey === 'end_ref_image_urls' && shot.image_url) {
            // Check if explicitly deleted
            const deleted = tech.deleted_ref_urls || [];
            const isExplicitlyDeleted = deleted.includes(shot.image_url);
            let hasStartFrame = activeRefs.includes(shot.image_url);

            if (!hasStartFrame && !isExplicitlyDeleted) {
                activeRefs.unshift(shot.image_url); // Prepend Start Frame for context
                hasStartFrame = true;
            }

            if (hasStartFrame && environmentRefSet.size > 0) {
                activeRefs = activeRefs.filter((url) => {
                    const normalized = String(url || '').trim();
                    if (!normalized) return false;
                    if (normalized === shot.image_url) return true;
                    return !environmentRefSet.has(normalized);
                });
            }
        }
        
        // 3. Special Logic for Video Refs: Only visual assets
        if (storageKey === 'video_ref_image_urls') {
             // For video, we largely ignore user manual list if it contradicts the generated assets flow?
             // Actually, if user customized it, we should respect it?
             // But the code previously cleared it in Auto mode.
             // Let's keep logic simple: If Video Mode, we assume strict structural refs.
             // But if user manually added strict refs, we keep them?
             // Reverting to previous strict logic for video mode seems safer to avoid "entity pollution".
                 if (!tech[storageKey] && !isLockedManual) {
                activeRefs = [];
                if (shot.image_url) activeRefs.push(shot.image_url);
                if (tech.keyframes && Array.isArray(tech.keyframes)) activeRefs.push(...tech.keyframes);
                if (tech.end_frame_url) activeRefs.push(tech.end_frame_url);
                 } else if (!isLockedManual && isManualMode && shot.image_url && !activeRefs.includes(shot.image_url)) {
                // Ensure Start Frame is visible even in Manual Mode if user didn't explicitly remove it? 
                // Wait - logic above says inject into Auto Only. 
                // If Manual Mode, we trust the list.
                // However user says: "Refs (End)引用首帧时不能实时更新，但Refs (Video)可以"
                // This means when shot.image_url changes, it doesn't show up in Refs(End) if it was already in Manual Mode or Auto Mode didn't catch it?
                
                // If in Auto Mode, the `shot.image_url` is added via Rule #2.
                // If in Manual Mode, `activeRefs` comes from `tech[storageKey]`.
                // If `shot.image_url` changes, `tech[storageKey]` is STALE.
                
                // We must Inject/Update Start Frame in Manual Mode too if it's missing or different?
                // But we don't know if user DELETED it.
                // Compromise: If Start Frame exists, we PREPEND it visually if likely candidates match, 
                // OR we just rely on the fact that if it's "Start Frame", it should always be there for End Gen context.
             }
        }
        
        // FIX FOR REFS (END) NOT UPDATING:
        // Refs (Video) works because we likely force it or it's using a different path.
        // Actually, looking at "Refs (Video)" logic above (lines 1190+), if no manual list, it rebuilds completely including `shot.image_url`.
        // "Refs (End)" logic (line 1175): Only injects `shot.image_url` IF `!activeRefs.includes`.
        
        // Critical Issue: `activeRefs` in Auto Mode comes from `getEntityMatches()` (entity images). 
        // Then we unshift `shot.image_url`.
        // If `shot.image_url` changes, the component re-renders. 
        // `activeRefs` is rebuilt. `shot.image_url` is new. It gets pushed.
        
        // HOWEVER, if Manual Mode (`end_ref_image_urls` exists):
        // `activeRefs` = loaded from DB.
        // If DB has OLD start frame url, and `shot.image_url` is NEW, 
        // `!activeRefs.includes(shot.image_url)` is TRUE.
        // So we unshift the NEW url. 
        // But the OLD url is still there? 
        // Yes, duplicate if old one is just a string.
        
        // User complaint: "Can't realtime update". 
        // Maybe because `ReferenceManager` is memozied or `shot` prop isn't triggering deep update?
        // No, `shot` is passed new object.
        
        // Let's force ensure Start Frame is present for End Refs, similar to Video Refs logic?
        // Actually, the issue might be that we only apply Rule #2 in the `else` (Auto Mode) block from my previous edit.
        // I moved the injection rules INSIDE the `else` block to fix the "Delete" issue.
        // But this broke the "Realtime Update" for manual mode? 
        // If I generate a new Start Frame, I enter Manual Mode? No, generating keeps it in whatever mode.
        // But if I ever saved the list (e.g. by deleting something), I am in Manual Mode.
        // And in Manual Mode, I explicitly REMOVED the injection logic to support deletion.
        
        // Logic Conflict:
        // 1. User wants to DELETE items (requires Manual Mode where we don't Force-Inject).
        // 2. User wants REALTIME UPDATE of Start Frame (requires Force-Injection whenever it changes).
        
        // Resolution:
        // We should identify the "Start Frame" in the list and REPLACE it if it changes, rather than blindly injecting.
        // OR: We only auto-inject into Manual Mode IF the list doesn't contain the *current* start frame.
        // BUT if user deleted it, we re-inject it? That creates the Zombie bug again.
        
        // Correct Approach for "Refs (End)" (Contextual Refs):
        // The Start Frame is a *Dependency*, not just a suggestion.
        // For End Frame generation, you almost ALWAYS want the Start Frame.
        // If the Start Frame updates, the Ref list *should* update to reflect the new reality.
        
        // What if we separate "Hard Dependencies" (Start Frame) from "Soft References" (Style/Entities)?
        // In the UI, we could show Start Frame as a pinned item?
        
        // Current quick fix:
        // Re-enable Injection for Manual Mode but be smarter?
        // OR: Just move the Rule #2 OUT of the `else` block (make it Global again) but check for *stale* versions?
        // For End Refs, the "Start Frame" is key.
        // If I move Rule #2 back out, deleting it becomes impossible because it re-injects.
        
        // Maybe we just allow Deleting it -> adds to an "Ignore List"? Too complex.
        
        // Let's look at "Refs (Video)".
        // It has logic: `if (!tech[storageKey]) { ...rebuild... }`
        // If Manual Mode, it uses `tech[storageKey]`.
        // Does "Refs (Video)" update start frame in Manual Mode?
        // If I have manual video refs, and I update start frame, does it update?
        // If logic is same, it shouldn't.
        // User says "Refs (Video) works". 
        // Maybe because they haven't triggered Manual Mode for Video yet?
        
        // Let's Apply the "Update Logic" specifically for Start Frame replacement.
        // If we find an item in `activeRefs` that LOOKS like a start frame (maybe check previous `shot` state? We don't have it).
        
        // Alternative:
        // We assume `shot.image_url` IS the single truth for the Start Frame dependency.
        // We simply render it as a "System Pinned" reference that cannot be removed? 
        // No, user wants to remove "Start" from "Refs (Start)" previously.
        // But for "Refs (End)", Start Frame is external context.
        
        // Let's try moving Rule #2 back to Global Scope (apply to Manual too), 
        // BUT make `ReferenceManager` smart enough to not resurrect it if *explicitly removed* in this session?
        // Hard to track session.
        
        // Let's strictly follow the request: "Refs (End) ... Refs (Video) worked".
        // Let's see if I can simply enable the injection for Manual Mode ONLY IF it's "Refs (End)" or "Refs (Video)" (for start frame).
        // And accept that Deleting it might be tricky?
        // Or better: Allow Deleting, but if a *New* Start Frame is generated, it comes back?
        // That happens naturally if `shot.image_url` changes value.
        
        // Let's try:
        // Move the Injection Rule for `end_ref_image_urls` + `shot.image_url` OUTSIDE the else block.
        // To prevent "Cannot Delete" Zombie bug:
        // The user was likely complaining about "Refs (Start)" (Start Frame generation refs).
        // "Refs (End)" (End Frame generation refs) *needs* the Start Frame.
        // The previous Zombie bug report was "Refs (Start) delete button invalid". 
        // "Refs (Start)" uses `additionalAutoRefs` (Previous Shot End Frame).
        // It does NOT use `shot.image_url` as a ref (it IS the result).
        
        // So:
        // Rule 1 (Additional Auto Refs - e.g. Prev Shot): Kept inside `else` (Auto only). Fixes "Refs (Start)" delete bug.
        // Rule 2 (Start Frame for End/Video Refs): Move OUTSIDE `else` (Global). 
        // This ensures Start Frame always appears in End/Video refs, updating in real-time.
        // Does this prevent deletion of Start Frame from End Refs? Yes.
        // Is that acceptable? Usually yes, Start Frame is the anchor for End Frame.
        // If user wants to generate End Frame *without* Start Frame context... that's rare?
        // If they really want to, they might struggle. But this fixes the "Update" issue.
        
        // Let's move Rule 2 out.
        
        // 3. Special Logic for Entity Refs mode: prompt-matched entity images + structural frames
        if (storageKey === 'video_ref_image_urls') {
            if (!isLockedManual) {
                activeRefs = buildAutoVideoRefList(shot, tech, resolvedVideoMode, getVideoPromptEntityRefs());
            }
        }
        
        // Deduplicate
        activeRefs = [...new Set(activeRefs)];
    }
    
    // Filter matches that are NOT already active to display as suggestions (Standard Mode Only)
    // USER REQUEST: Show detected entities as suggestions even if in Manual Mode, so user can add them.
    // UPDATE: Detected entities are now auto-merged into activeRefs (unless deleted), so availableMatches logic is minimized.
    // Note: Video Refs totally skip entity matching.
    const entityMatches = useSequenceLogic ? [] : getEntityMatches();
    const availableMatches = entityMatches.filter(e => {
        // Technically these are items that matched but are NOT in activeRefs.
        // This only happens if they have no image OR were explicitly deleted.
        return !!e.image_url && !activeRefs.includes(e.image_url);
    });

    const handleAdd = (url) => {
        if (!url || activeRefs.includes(url)) return;
        const newRefList = [...activeRefs, url];
        // If sequential, do we save back to ref_image_urls? 
        // User request implies the LOGIC for getting pics is fixed. 
        // So for "Refs (Video)", maybe we don't save to 'ref_image_urls' necessarily, 
        // OR we overwrite 'ref_image_urls' with this sequence so backend uses it?
        // Let's assume we update the standard field so backend picks it up easily.
        const userEditedKey = `${storageKey}_user_edited`;
        const newTech = { ...tech, [storageKey]: newRefList, [userEditedKey]: true };
        if (isVideoRefManager) {
            newTech.video_ref_image_urls_manual = true;
        }
        onUpdate({ technical_notes: JSON.stringify(newTech) });
    };

    const handleRemove = (url) => {
        if (useSequenceLogic) return; // Cannot remove derived items in this view
        
        // Track deletions to prevent zombie resurrection by auto-injection
        let deleted = tech.deleted_ref_urls || [];
        if (!deleted.includes(url)) {
            deleted = [...deleted, url];
        }

        const newRefs = activeRefs.filter(u => u !== url);
        const userEditedKey = `${storageKey}_user_edited`;
        const newTech = { ...tech, [storageKey]: newRefs, deleted_ref_urls: deleted, [userEditedKey]: true };
        if (isVideoRefManager) {
            newTech.video_ref_image_urls_manual = true;
        }
        onUpdate({ technical_notes: JSON.stringify(newTech) });
    };

    const getEntityInfo = (url) => {
        return entities.find(e => e.image_url === url);
    };

    const currentSubmitRefCount = activeRefs.length;

    // Modal Content
    const renderModal = () => {
        if (!selectedImage) return null;
        
        const entity = getEntityInfo(selectedImage);
        
        return (
              <div className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 sm:p-8" onClick={() => setSelectedImage(null)}>
                  <div className="bg-[#1a1a1a] border border-white/10 rounded-xl overflow-hidden max-w-5xl w-full max-h-[90vh] flex flex-col lg:flex-row shadow-2xl" onClick={e => e.stopPropagation()}>
                    {/* Image Area */}
                    <div className="flex-1 bg-black/50 flex items-center justify-center p-4 relative group/modal">
                        <SafeImage src={selectedImage} className="max-w-full max-h-full object-contain shadow-lg rounded" alt="Detail" />
                        <button 
                            className="absolute top-4 right-4 bg-black/50 text-white p-2 rounded-full hover:bg-white/20 transition-colors"
                            onClick={() => setSelectedImage(null)}
                        >
                            <X size={24} />
                        </button>
                    </div>

                    {/* Metadata Sidebar */}
                    <div className="w-full lg:w-80 bg-[#151515] border-t lg:border-t-0 lg:border-l border-white/10 p-4 sm:p-6 flex flex-col gap-4 overflow-y-auto max-h-[40vh] lg:max-h-none">
                        <div>
                            <h3 className="text-xl font-bold text-white mb-1">{entity?.name || 'External Image'}</h3>
                            {entity?.name_en && <div className="text-sm text-muted-foreground">{entity.name_en}</div>}
                        </div>

                        <div className="space-y-4">
                            {entity ? (
                                <>
                                    <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                                        <span className="text-[10px] uppercase font-bold text-primary/70 block mb-1">{t('描述', 'Description')}</span>
                                        <p className="text-sm text-gray-300 leading-relaxed max-h-[200px] overflow-y-auto custom-scrollbar">
                                            {entity.description || 'No description available.'}
                                        </p>
                                    </div>
                                    
                                    <div className="grid grid-cols-2 gap-2">
                                        <div className="bg-white/5 p-2 rounded border border-white/5">
                                            <span className="text-[10px] uppercase text-gray-500 block">{t('类型', 'Type')}</span>
                                            <span className="text-xs text-gray-300">{entity.type || 'Unknown'}</span>
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="text-sm text-muted-foreground italic">
                                    This image was added via URL or is external to the entity library. Metadata is unavailable.
                                </div>
                            )}

                            {/* Actions */}
                            <div className="pt-4 mt-auto border-t border-white/10 flex flex-col gap-2">
                                {activeRefs.includes(selectedImage) ? (
                                    <button 
                                        onClick={() => { handleRemove(selectedImage); setSelectedImage(null); }}
                                        className="w-full py-2 bg-red-500/10 text-red-400 border border-red-500/30 rounded flex items-center justify-center gap-2 hover:bg-red-500/20 text-sm font-medium"
                                    >
                                        <Trash2 size={16} /> Remove Reference
                                    </button>
                                ) : (
                                     <button 
                                        onClick={() => { handleAdd(selectedImage); }} // Update status, keep modal open to show it's active now
                                        className="w-full py-2 bg-primary/10 text-primary border border-primary/30 rounded flex items-center justify-center gap-2 hover:bg-primary/20 text-sm font-medium"
                                    >
                                        <Plus size={16} /> Add to References
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                 </div>
            </div>
        )
    }

    return (
        <>
            {renderModal()}
            <div className="space-y-2 pb-4 border-b border-white/10 mb-4">
                <div className="flex items-center justify-between">
                     <h4 className="text-xs font-bold text-muted-foreground uppercase flex items-center gap-2">
                        {title}
                        {isVideoManualOverride && (
                            <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[9px] font-bold text-amber-200 normal-case">
                                {t('手工调整', 'Manual')}
                            </span>
                        )}
                        {onFindPrevFrame && (
                            <button 
                                onClick={(e) => {
                                    e.stopPropagation();
                                    const url = onFindPrevFrame();
                                    if (url) handleAdd(url);
                                }}
                                className="p-1 bg-white/5 hover:bg-primary/20 text-white/70 hover:text-primary rounded transition-colors"
                                title={t('获取上一镜头结束帧', 'Fetch Previous Shot End Frame')}
                            >
                                <ArrowUp className="w-3 h-3" />
                            </button>
                        )}
                    </h4>
                    <div className="flex items-center gap-1.5">
                        <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded text-white/50">Used by AI: {activeRefs.length}</span>
                        {isVideoRefManager && (
                            <span className="text-[10px] bg-primary/15 border border-primary/30 px-1.5 py-0.5 rounded text-primary/90">
                                {t(`当前提交引用数 = ${currentSubmitRefCount}`, `Current submit ref count = ${currentSubmitRefCount}`)}
                            </span>
                        )}
                    </div>
                </div>
                
                <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar min-h-[90px]">
                    {/* 1. Active Refs (Selected) */}
                    {activeRefs.map((url, idx) => (
                        <div key={url + idx} className="relative group shrink-0 w-[140px] aspect-video bg-black/40 rounded border border-primary/50 overflow-hidden shadow-[0_0_10px_rgba(0,0,0,0.5)] cursor-zoom-in" onClick={() => setSelectedImage(url)}>
                            {(url.toLowerCase().endsWith('.mp4') || url.toLowerCase().endsWith('.webm')) ? (
                                <LazyHoverVideo
                                    src={url}
                                    className="w-full h-full flex items-center justify-center"
                                    mediaClassName="w-full h-full object-contain object-center"
                                    muted
                                    loop
                                    playsInline
                                    playOnHover
                                    resetOnLeave
                                />
                            ) : (
                                <SafeImage src={url} className="w-full h-full object-contain object-center" alt="ref" />
                            )}
                            {!useSequenceLogic && (
                                <button 
                                    onClick={(e) => { e.stopPropagation(); handleRemove(url); }}
                                    className="absolute top-1 right-1 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:scale-110 z-10"
                                >
                                    <X className="w-3 h-3"/>
                                </button>
                            )}
                        </div>
                    ))}
                    
                    {/* Add Button */}
                    {!useSequenceLogic && onPickMedia && (
                        <button 
                            onClick={() => onPickMedia((url) => handleAdd(url), { shotId: shot?.id })}
                            className="shrink-0 w-[50px] aspect-video bg-white/5 hover:bg-white/10 border border-white/10 border-dashed rounded flex flex-col items-center justify-center gap-1 text-muted-foreground hover:text-white transition-colors"
                            title={t('从素材中选择', 'Pick from Assets')}
                        >
                            <Plus className="w-5 h-5"/>
                        </button>
                    )}
                </div>
            </div>
        </>
    )
};

export const SceneCard = ({ scene, entities, shotCount = 0, onClick, onGenerateShots, onSupplementShots, onDelete, selected = false, onToggleSelect, uiLang = 'zh', generatingShots = false, subjectGap = null, onSupplementSubjects = null, supplementingSubjects = false }) => {
    const [images, setImages] = useState([]);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isShotMenuOpen, setIsShotMenuOpen] = useState(false);
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);

    useEffect(() => {
        // Parse logic
        const sourceText = scene.environment_name || scene.location || '';
        let anchors = [];
        const bracketMatches = sourceText.match(/\[(.*?)\]/g);
        if (bracketMatches && bracketMatches.length > 0) {
            anchors = bracketMatches.map(m => m.replace(/[\[\]\*]/g, '').trim());
        } else {
            anchors = sourceText.split(/[,，]/).map(s => s.replace(/[\*]/g, '').trim()).filter(Boolean);
        }

        const validUrls = [];
        // Updated cleaner: Removes whitespace to handle "主视角" vs "主视角 " mismatch
        const cleanForMatch = (str) => (str || '').replace(/[（\(\)）\s]/g, '').toLowerCase();

        anchors.forEach(rawLoc => {
            const targetName = cleanForMatch(rawLoc);
            if (!targetName) return;

             // Logic extracted from getSceneImages
            let match = entities.find(e => {
                const cn = cleanForMatch(e.name);
                let en = (e.name_en || '').toLowerCase();
                if (!en && e.description) {
                    const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                    if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                }
                const enClean = cleanForMatch(en);
                return cn === targetName || enClean === targetName;
            });

            if (!match) {
                 match = entities.find(e => {
                    const cn = cleanForMatch(e.name);
                    let en = (e.name_en || '').toLowerCase();
                    if (!en && e.description) {
                        const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                        if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                    }
                    const enClean = cleanForMatch(en);
                    return (cn && (cn.includes(targetName) || targetName.includes(cn))) ||
                           (enClean && (enClean.includes(targetName) || targetName.includes(enClean)));
                 });
            }
            if (match && match.image_url && !isBrokenSceneImageUrl(match.image_url)) validUrls.push(match.image_url);
        });

        // Use Set to remove duplicates
        setImages([...new Set(validUrls)]);
        setCurrentIndex(0);
    }, [scene, entities]);

    useEffect(() => {
        if (images.length <= 1) return;
        const interval = setInterval(() => {
            setCurrentIndex(prev => (prev + 1) % images.length);
        }, 3000);
        return () => clearInterval(interval);
    }, [images]);

    const handleGenerate = async (e) => {
        e.stopPropagation();
        if (isGenerating || generatingShots) return;
        setIsShotMenuOpen(false);
        setIsGenerating(true);
        try {
            if (onGenerateShots) {
                await onGenerateShots(scene.id);
            }
        } finally {
            setIsGenerating(false);
        }
    };

    const handleSupplement = async (e) => {
        e.stopPropagation();
        setIsShotMenuOpen(false);
        if (typeof onSupplementShots === 'function') {
            await onSupplementShots(scene);
        }
    };

    const handleDelete = async (e) => {
        e.stopPropagation();
        setIsShotMenuOpen(false);
        if (!onDelete || !scene?.id) return;
        await onDelete(scene);
    };

    const handleSupplementSubjects = async (e) => {
        e.stopPropagation();
        if (typeof onSupplementSubjects === 'function') {
            await onSupplementSubjects(scene, subjectGap);
        }
    };

    const handleToggleSelect = (e) => {
        e.stopPropagation();
        if (typeof onToggleSelect === 'function') onToggleSelect(scene);
    };

    const imgUrl = images.length > 0 ? images[currentIndex] : null;
    const shotsBusy = isGenerating || generatingShots;
    const missingSubjectCount = Number(subjectGap?.missing?.length || 0);
    const missingSubjectTitle = missingSubjectCount > 0
        ? subjectGap.missing.map((item) => `${item.type}: ${item.name}`).join('\n')
        : '';
    const handleSceneImageError = () => {
        if (!imgUrl) return;
        rememberBrokenSceneImageUrl(imgUrl);
        setImages((prev) => prev.filter((url) => String(url || '').trim() !== String(imgUrl || '').trim()));
        setCurrentIndex(0);
    };

    return (
        <div 
            className="bg-card/80 backdrop-blur-sm rounded-xl border border-white/10 overflow-hidden group hover:border-primary/50 transition-all cursor-pointer relative flex flex-col"
            onClick={onClick}
        >
            <div className="aspect-video bg-black/60 flex items-center justify-center text-muted-foreground relative group-hover:bg-black/40 transition-colors overflow-hidden border-b border-white/10">
                {imgUrl ? (
                    <motion.img 
                        key={imgUrl}
                        src={getFullUrl(imgUrl)} 
                        onError={handleSceneImageError}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.5 }}
                        className="w-full h-full object-cover absolute inset-0" 
                        alt={scene.scene_name}
                    />
                ) : (
                    <div className="flex flex-col items-center gap-2 opacity-50">
                        <ImageIcon className="w-8 h-8" />
                        <span className="text-xs">{t('无环境图', 'No Env Image')}</span>
                    </div>
                )}
                
                {/* Dots indicator for multiple images */}
                {images.length > 1 && (
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1 z-10">
                        {images.map((_, idx) => (
                            <div key={idx} className={`w-1.5 h-1.5 rounded-full ${idx === currentIndex ? 'bg-primary' : 'bg-white/50'}`} />
                        ))}
                    </div>
                )}

                <label
                    className="absolute top-2 left-2 z-30 flex items-center justify-center w-6 h-6 rounded bg-black/60 border border-white/20 cursor-pointer shadow"
                    title={t('选择场景', 'Select scene')}
                >
                    <input
                        type="checkbox"
                        checked={!!selected}
                        onChange={handleToggleSelect}
                        className="accent-primary"
                    />
                </label>

                <div className="absolute top-2 left-10 bg-black/60 px-2 py-1 rounded text-xs font-mono font-bold text-white border border-white/10 z-10 max-w-[70%] truncate shadow">
                    {scene.scene_no || scene.id}
                </div>
                <div className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="flex items-center gap-1 relative">
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setIsShotMenuOpen((prev) => !prev);
                            }}
                            className="bg-black/70 hover:bg-black text-white px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 shadow-lg border border-white/10"
                            title={t('镜头菜单', 'Shot Menu')}
                        >
                            <MoreHorizontal className="w-3 h-3" />
                            {t('镜头', 'Shots')}
                        </button>
                        {isShotMenuOpen && (
                            <div className="absolute top-full right-0 mt-1 min-w-[148px] rounded-lg border border-white/10 bg-[#111111] shadow-2xl overflow-hidden">
                                <button
                                    onClick={handleGenerate}
                                    disabled={shotsBusy}
                                    className="w-full px-3 py-2 text-left text-[11px] text-white/90 hover:bg-white/10 flex items-center gap-2 disabled:opacity-50"
                                >
                                    {shotsBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                                    {shotsBusy ? t('生成中...', 'Generating...') : t('AI 镜头', 'AI Shots')}
                                </button>
                                <button
                                    onClick={handleSupplement}
                                    className="w-full px-3 py-2 text-left text-[11px] text-amber-100 hover:bg-amber-500/10 flex items-center gap-2"
                                >
                                    <Sparkles className="w-3 h-3" />
                                    {t('补充镜头', 'Supplement Shots')}
                                </button>
                            </div>
                        )}
                        <button
                            onClick={handleDelete}
                            className="bg-red-500/90 hover:bg-red-500 text-white px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 shadow-lg"
                            title={t('删除场景', 'Delete Scene')}
                        >
                            <Trash2 className="w-3 h-3"/>
                            {t('删除', 'Delete')}
                        </button>
                        <button 
                            onClick={handleGenerate}
                            disabled={shotsBusy}
                            className="bg-primary/90 hover:bg-primary text-black px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 shadow-lg"
                            title={t('AI 生成镜头列表', 'AI Generate Shot List')}
                        >
                            {shotsBusy ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                            {shotsBusy ? t('生成中...', 'Generating...') : t('AI 镜头', 'AI Shots')}
                        </button>
                    </div>
                </div>
                <div className="absolute bottom-2 right-2 bg-primary text-black px-2 py-0.5 rounded text-[10px] font-bold z-10">
                    {scene.equivalent_duration || '0m'}
                </div>
            </div>
            
            <div className="p-3 space-y-3 flex-1 flex flex-col">
                <div className="space-y-1">
                    <div className="flex items-center gap-2 min-w-0">
                        <h3 className="font-semibold text-sm text-white line-clamp-1 min-w-0" title={scene.scene_name}>{scene.scene_name || t('未命名场景', 'Untitled Scene')}</h3>
                        {missingSubjectCount > 0 && (
                            <button
                                type="button"
                                onClick={handleSupplementSubjects}
                                disabled={supplementingSubjects}
                                className="shrink-0 inline-flex items-center gap-1 rounded-full border border-amber-400/30 bg-amber-400/12 px-2 py-0.5 text-[10px] font-semibold text-amber-100 hover:bg-amber-400/20 disabled:opacity-60 disabled:cursor-not-allowed"
                                title={missingSubjectTitle || t('存在缺失 subjects，点击补充实体', 'Missing subjects detected. Click to supplement entities.')}
                            >
                                {supplementingSubjects ? <Loader2 className="w-3 h-3 animate-spin" /> : <AlertTriangle className="w-3 h-3" />}
                                <span>{missingSubjectCount}</span>
                            </button>
                        )}
                    </div>
                    <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
                        <div className="truncate min-w-0">
                            <span className="opacity-60">{t('环境：', 'Env:')}</span>{' '}
                            <span className="text-white/70" title={scene.environment_name}>{scene.environment_name || '-'}</span>
                        </div>
                        <div className="shrink-0 inline-flex items-center gap-1 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2 py-0.5 text-cyan-100">
                            <Film className="w-3 h-3" />
                            <span>{shotCount}</span>
                            <span className="opacity-80">{t('分镜', 'Shots')}</span>
                        </div>
                    </div>
                </div>

                <div className="text-xs text-muted-foreground space-y-2 flex-1 min-h-0">
                    <div className="bg-white/5 p-2 rounded border border-white/5 relative">
                        <span className="font-bold text-white/50 block text-[10px] uppercase mb-1">{t('核心信息', 'Core Info')}</span>
                        <div className="h-[60px] overflow-hidden text-white/80 leading-normal prose prose-invert prose-p:my-0 prose-p:leading-normal prose-headings:my-0 prose-ul:my-0 prose-li:my-0 text-[11px]">
                            <ReactMarkdown components={{
                                p: ({node, ...props}) => <p className="mb-1" {...props} />
                            }}>{scene.core_scene_info || t('暂无核心信息', 'No core info')}</ReactMarkdown>
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        {missingSubjectCount > 0 && (
                            <button
                                type="button"
                                onClick={handleSupplementSubjects}
                                disabled={supplementingSubjects}
                                className="w-full text-left rounded-lg border border-amber-400/20 bg-amber-400/10 px-2 py-1.5 text-[10px] text-amber-100 hover:bg-amber-400/15 disabled:opacity-60 disabled:cursor-not-allowed"
                                title={missingSubjectTitle}
                            >
                                <div className="flex items-center gap-1 font-semibold">
                                    {supplementingSubjects ? <Loader2 className="w-3 h-3 animate-spin" /> : <AlertTriangle className="w-3 h-3" />}
                                    <span>{t(`缺失 ${missingSubjectCount} 个 subjects，点击一键补齐实体`, `Missing ${missingSubjectCount} subjects. Click to supplement entities.`)}</span>
                                </div>
                                <div className="mt-1 line-clamp-2 text-amber-50/80">{subjectGap?.missing?.map((item) => item.name).join(' / ')}</div>
                            </button>
                        )}
                        {(scene.linked_characters || scene.key_props) ? (
                            <>
                            {scene.linked_characters && (
                                <div className="flex flex-col gap-0.5">
                                    <span className="font-bold text-white/40 text-[9px] uppercase">{t('角色', 'Cast')}</span>
                                    <div className="flex flex-wrap gap-1">
                                        {scene.linked_characters.split(/[，,]/).filter(Boolean).map((char, i) => (
                                            <span key={i} className="inline-block bg-indigo-500/20 text-indigo-200 border border-indigo-500/30 px-1.5 py-0.5 rounded text-[10px]">
                                                {char.trim()}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {scene.key_props && (
                                <div className="flex flex-col gap-0.5">
                                    <span className="font-bold text-white/40 text-[9px] uppercase">{t('道具', 'Props')}</span>
                                    <div className="flex flex-wrap gap-1">
                                        {scene.key_props.split(/[，,]/).filter(Boolean).map((prop, i) => (
                                            <span key={i} className="inline-block bg-emerald-500/20 text-emerald-200 border border-emerald-500/30 px-1.5 py-0.5 rounded text-[10px]">
                                                {prop.trim()}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            </>
                        ) : (
                             <div className="line-clamp-2 opacity-50 italic text-[11px]">
                                {scene.original_script_text || t('暂无描述', 'No description')}
                            </div>
                        )}
                    </div>
                </div>

                <div className="pt-2 border-t border-white/5 mt-auto">
                    <div className="grid grid-cols-3 gap-2">
                        <button
                            onClick={handleGenerate}
                            disabled={shotsBusy}
                            className="bg-primary/85 hover:bg-primary text-black px-2 py-1.5 rounded text-[11px] font-semibold flex items-center justify-center gap-1 disabled:opacity-60"
                            title={t('AI 生成镜头列表', 'AI Generate Shot List')}
                        >
                            {shotsBusy ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                            {shotsBusy ? t('生成中...', 'Generating...') : t('AI 镜头', 'AI Shots')}
                        </button>
                        <button
                            onClick={handleSupplement}
                            className="bg-amber-500/20 hover:bg-amber-500/30 text-amber-100 border border-amber-500/30 px-2 py-1.5 rounded text-[11px] font-semibold flex items-center justify-center gap-1"
                            title={t('打开补充镜头菜单', 'Open shot supplement flow')}
                        >
                            <Sparkles className="w-3 h-3"/>
                            {t('补充镜头', 'Supplement')}
                        </button>
                        <button
                            onClick={handleDelete}
                            className="bg-red-500/20 hover:bg-red-500/30 text-red-200 border border-red-500/30 px-2 py-1.5 rounded text-[11px] font-semibold flex items-center justify-center gap-1"
                            title={t('删除场景', 'Delete Scene')}
                        >
                            <Trash2 className="w-3 h-3"/>
                            {t('删除', 'Delete')}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export const SceneManager = ({ activeEpisode, projectId, project, onLog, onImportText, onSwitchToShots, uiLang = 'zh' }) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const defaultSceneRegenRequirement = t('补充所缺实体', 'Supplement missing entities');
    const SCENE_AI_SHOTS_BATCH_KIND = 'scene-ai-shots-batch';
    const SCENE_AI_SHOTS_RUNTIME_TTL_MS = 1000 * 60 * 60 * 6;
    const ANALYSIS_TASK_MAX_AGE_MS = 10 * 60 * 1000;
    const AI_SHOTS_TASK_MARKER_TTL_MS = 12 * 60 * 1000;
    const createBatchAiShotsProgressState = () => ({
        running: false,
        total: 0,
        completed: 0,
        success: 0,
        failed: 0,
        stopRequested: false,
        currentSceneLabel: '',
        message: '',
        errors: [],
    });
    const [scenes, setScenes] = useState([]);
    const [sceneShotCountMap, setSceneShotCountMap] = useState({});
    const [sceneListLoading, setSceneListLoading] = useState(false);
    const [sceneSortMode, setSceneSortMode] = useState('updated_desc');
    const [sceneSortDirection, setSceneSortDirection] = useState('desc');
    const [selectedSceneKeys, setSelectedSceneKeys] = useState([]);
    const [entities, setEntities] = useState([]);
    const [sceneSubjectSupplementingMap, setSceneSubjectSupplementingMap] = useState({});
    const [isSuperuser, setIsSuperuser] = useState(false);
    const [editingScene, setEditingScene] = useState(null);
    const [sceneRegenRequirements, setSceneRegenRequirements] = useState('');
    const [sceneRegenEntityOnlyMode, setSceneRegenEntityOnlyMode] = useState(true);
    const [sceneRegenerating, setSceneRegenerating] = useState(false);
    const [sceneRegenPromptModal, setSceneRegenPromptModal] = useState({
        open: false,
        loading: false,
        data: null,
    });
    const [sceneRegenProgress, setSceneRegenProgress] = useState({
        phase: 'idle',
        percent: 0,
        message: '',
        error: '',
    });
    const [sceneRegenSubjectsReport, setSceneRegenSubjectsReport] = useState(null);
    const [sceneRegenReimporting, setSceneRegenReimporting] = useState(false);
    const [sceneRegenScenePatching, setSceneRegenScenePatching] = useState(false);
    const [shotPromptModal, setShotPromptModal] = useState({ open: false, sceneId: null, data: null, loading: false });
    const [shotRegenModal, setShotRegenModal] = useState({
        open: false,
        sceneId: null,
        instructions: '',
        submitting: false,
        error: '',
    });
    const [pendingShotSupplementSceneId, setPendingShotSupplementSceneId] = useState(null);
    const [shotSupplementImportReport, setShotSupplementImportReport] = useState(null);
    const [aiShotsFlowStatus, setAiShotsFlowStatus] = useState({ phase: 'idle', message: '', sceneId: null });
    const aiShotsBusySceneIdsRef = useRef(new Set());
    const aiShotsPromptPreviewSceneIdsRef = useRef(new Set());
    const [batchAiShotsProgress, setBatchAiShotsProgress] = useState(() => createBatchAiShotsProgressState());
    const [isSceneBatchProgressDismissed, setIsSceneBatchProgressDismissed] = useState(false);
    const [isStoppingBatchAiShots, setIsStoppingBatchAiShots] = useState(false);
    const batchAiShotsStatusTimerRef = useRef(null);
    const batchAiShotsStartupGuardUntilRef = useRef(0);
    const batchAiShotsBootstrapUntilRef = useRef(0);
    const batchAiShotsProgressRef = useRef(createBatchAiShotsProgressState());
    const recoverBatchAiShotsInFlightRef = useRef(false);
    const recoverBatchAiShotsLastAtRef = useRef(0);
    const aiShotsResumeInFlightRef = useRef(false);
    const [aiShotsStaging, setAiShotsStaging] = useState({
        loading: false,
        sceneId: null,
        content: [],
        rawText: '',
        usage: null,
        timestamp: null,
        warnings: [],
        error: null,
        saving: false,
        applying: false,
    });
    const [aiShotRowEditor, setAiShotRowEditor] = useState({
        open: false,
        index: -1,
        data: null,
    });
    const sceneIdSignature = useMemo(
        () => (Array.isArray(scenes)
            ? scenes
                .map((scene) => Number(scene?.id || 0))
                .filter((id) => id > 0)
                .sort((left, right) => left - right)
                .join(',')
            : ''),
        [scenes]
    );

    const refreshSceneShotCounts = useCallback(async () => {
        if (!activeEpisode?.id) {
            setSceneShotCountMap({});
            return;
        }
        try {
            const rows = await fetchEpisodeShots(activeEpisode.id, { compact: true });
            const nextCounts = {};
            (Array.isArray(rows) ? rows : []).forEach((shot) => {
                const sceneId = Number(shot?.scene_id || 0);
                if (sceneId <= 0) return;
                nextCounts[sceneId] = (nextCounts[sceneId] || 0) + 1;
            });
            setSceneShotCountMap(nextCounts);
        } catch (e) {
            console.warn('Failed to refresh scene shot counts', e);
            setSceneShotCountMap({});
        }
    }, [activeEpisode?.id]);

    const getAiShotsTaskStorageKey = useCallback((episodeId, sceneId) => {
        if (!episodeId || !sceneId) return '';
        return `aistory:scene-ai-shots-task:${episodeId}:scene:${sceneId}`;
    }, []);

    const getAiShotsTaskActiveSceneKey = useCallback((episodeId) => {
        if (!episodeId) return '';
        return `aistory:scene-ai-shots-task-active-scene:${episodeId}`;
    }, []);

    const getAiShotsAutoSwitchTicketKey = useCallback((episodeId) => {
        if (!episodeId) return '';
        return `aistory:scene-ai-shots-auto-switch-ticket:${episodeId}`;
    }, []);

    const getBatchAiShotsRuntimeStorageKey = useCallback((episodeId) => {
        if (!episodeId) return '';
        return `aistory:scene-ai-shots-progress:${episodeId}`;
    }, []);

    const loadBatchAiShotsRuntime = useCallback((episodeId) => {
        try {
            const key = getBatchAiShotsRuntimeStorageKey(episodeId);
            if (!key || !window?.localStorage) return null;
            const raw = window.localStorage.getItem(key);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            const updatedAt = Number(parsed?.updatedAt || 0);
            if (!Number.isFinite(updatedAt) || updatedAt <= 0) return null;
            if ((Date.now() - updatedAt) > SCENE_AI_SHOTS_RUNTIME_TTL_MS) {
                window.localStorage.removeItem(key);
                return null;
            }
            return {
                running: Boolean(parsed?.running),
                total: Number(parsed?.total || 0),
                completed: Number(parsed?.completed || 0),
                success: Number(parsed?.success || 0),
                failed: Number(parsed?.failed || 0),
                stopRequested: Boolean(parsed?.stopRequested),
                currentSceneLabel: String(parsed?.currentSceneLabel || ''),
                message: String(parsed?.message || ''),
                errors: Array.isArray(parsed?.errors) ? parsed.errors : [],
            };
        } catch (_) {
            return null;
        }
    }, [getBatchAiShotsRuntimeStorageKey, SCENE_AI_SHOTS_RUNTIME_TTL_MS]);

    const saveBatchAiShotsRuntime = useCallback((episodeId, progress) => {
        try {
            const key = getBatchAiShotsRuntimeStorageKey(episodeId);
            if (!key || !window?.localStorage) return;
            const payload = {
                running: Boolean(progress?.running),
                total: Number(progress?.total || 0),
                completed: Number(progress?.completed || 0),
                success: Number(progress?.success || 0),
                failed: Number(progress?.failed || 0),
                stopRequested: Boolean(progress?.stopRequested),
                currentSceneLabel: String(progress?.currentSceneLabel || ''),
                message: String(progress?.message || ''),
                errors: Array.isArray(progress?.errors) ? progress.errors : [],
                updatedAt: Date.now(),
            };
            window.localStorage.setItem(key, JSON.stringify(payload));
        } catch (_) {
            // Ignore localStorage failures.
        }
    }, [getBatchAiShotsRuntimeStorageKey]);

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

    const recoverBatchAiShotsFromJobPool = useCallback(async () => {
        if (!activeEpisode?.id) return false;
        const now = Date.now();
        if (recoverBatchAiShotsInFlightRef.current) return false;
        if ((now - Number(recoverBatchAiShotsLastAtRef.current || 0)) < 4000) return false;

        recoverBatchAiShotsInFlightRef.current = true;
        recoverBatchAiShotsLastAtRef.current = now;
        try {
            const data = await getGenerationJobPool({
                kind: SCENE_AI_SHOTS_BATCH_KIND,
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

            const running = String(matched?.status || '').toLowerCase() === 'running';
            if (!running) return false;

            setBatchAiShotsProgress((prev) => ({
                ...prev,
                running: true,
                message: String(prev?.message || t('检测到任务池中的批量任务，正在恢复进度...', 'Detected running batch task in job pool, restoring progress...')),
            }));
            return true;
        } catch (_) {
            return false;
        } finally {
            recoverBatchAiShotsInFlightRef.current = false;
        }
    }, [SCENE_AI_SHOTS_BATCH_KIND, activeEpisode?.id, extractEpisodeIdFromJobPoolItem, t]);

    const loadAiShotsTaskMarker = useCallback((episodeId, preferredSceneId = null) => {
        try {
            let stableSceneId = Number(preferredSceneId || 0);
            if (!Number.isFinite(stableSceneId) || stableSceneId <= 0) {
                const activeSceneKey = getAiShotsTaskActiveSceneKey(episodeId);
                if (activeSceneKey && window?.localStorage) {
                    const activeSceneRaw = window.localStorage.getItem(activeSceneKey);
                    stableSceneId = Number(activeSceneRaw || 0);
                }
            }
            if (!Number.isFinite(stableSceneId) || stableSceneId <= 0) return null;

            const key = getAiShotsTaskStorageKey(episodeId, stableSceneId);
            if (!key || !window?.localStorage) return null;
            const raw = window.localStorage.getItem(key);
            if (!raw) return null;

            const parsed = JSON.parse(raw);
            const taskId = String(parsed?.taskId || '').trim();
            const sceneId = Number(parsed?.sceneId || 0);
            const startedAt = Number(parsed?.startedAt || 0);
            if (!taskId || !Number.isFinite(sceneId) || sceneId <= 0) return null;

            const normalizedStartedAt = (Number.isFinite(startedAt) && startedAt > 0) ? startedAt : Date.now();
            // Align marker TTL with task polling timeout to avoid endless resume loops after reload.
            if ((Date.now() - normalizedStartedAt) > AI_SHOTS_TASK_MARKER_TTL_MS) {
                window.localStorage.removeItem(key);
                return null;
            }
            return { taskId, sceneId, startedAt: normalizedStartedAt };
        } catch (_) {
            return null;
        }
    }, [AI_SHOTS_TASK_MARKER_TTL_MS, getAiShotsTaskStorageKey, getAiShotsTaskActiveSceneKey]);

    const saveAiShotsTaskMarker = useCallback((episodeId, marker) => {
        try {
            const taskId = String(marker?.taskId || '').trim();
            const sceneId = Number(marker?.sceneId || 0);
            if (!taskId || !Number.isFinite(sceneId) || sceneId <= 0) return;
            const key = getAiShotsTaskStorageKey(episodeId, sceneId);
            if (!key || !window?.localStorage) return;
            const payload = {
                taskId,
                sceneId,
                startedAt: Number(marker?.startedAt || Date.now()),
            };
            window.localStorage.setItem(key, JSON.stringify(payload));
            const activeSceneKey = getAiShotsTaskActiveSceneKey(episodeId);
            if (activeSceneKey) {
                window.localStorage.setItem(activeSceneKey, String(sceneId));
            }
        } catch (_) {
            // Ignore localStorage failures.
        }
    }, [getAiShotsTaskStorageKey, getAiShotsTaskActiveSceneKey]);

    const clearAiShotsTaskMarker = useCallback((episodeId, sceneId = null) => {
        try {
            if (!window?.localStorage || !episodeId) return;

            const stableSceneId = Number(sceneId || 0);
            if (Number.isFinite(stableSceneId) && stableSceneId > 0) {
                const sceneKey = getAiShotsTaskStorageKey(episodeId, stableSceneId);
                if (sceneKey) window.localStorage.removeItem(sceneKey);
                const activeSceneKey = getAiShotsTaskActiveSceneKey(episodeId);
                if (activeSceneKey) {
                    const activeSceneRaw = Number(window.localStorage.getItem(activeSceneKey) || 0);
                    if (activeSceneRaw === stableSceneId) {
                        window.localStorage.removeItem(activeSceneKey);
                    }
                }
                return;
            }

            const activeSceneKey = getAiShotsTaskActiveSceneKey(episodeId);
            const activeSceneRaw = activeSceneKey ? Number(window.localStorage.getItem(activeSceneKey) || 0) : 0;
            if (Number.isFinite(activeSceneRaw) && activeSceneRaw > 0) {
                const sceneKey = getAiShotsTaskStorageKey(episodeId, activeSceneRaw);
                if (sceneKey) window.localStorage.removeItem(sceneKey);
            }
            if (activeSceneKey) window.localStorage.removeItem(activeSceneKey);
        } catch (_) {
            // Ignore localStorage failures.
        }
    }, [getAiShotsTaskStorageKey, getAiShotsTaskActiveSceneKey]);

    const armAiShotsAutoSwitchTicket = useCallback((episodeId, sceneId) => {
        try {
            if (!window?.localStorage || !episodeId) return;
            const key = getAiShotsAutoSwitchTicketKey(episodeId);
            if (!key) return;
            const payload = {
                armed: true,
                sceneId: Number(sceneId || 0),
                updatedAt: Date.now(),
            };
            window.localStorage.setItem(key, JSON.stringify(payload));
        } catch (_) {
            // Ignore localStorage failures.
        }
    }, [getAiShotsAutoSwitchTicketKey]);

    const consumeAiShotsAutoSwitchTicket = useCallback((episodeId) => {
        try {
            if (!window?.localStorage || !episodeId) return false;
            const key = getAiShotsAutoSwitchTicketKey(episodeId);
            if (!key) return false;
            const raw = window.localStorage.getItem(key);
            if (!raw) return false;

            const parsed = JSON.parse(raw);
            const armed = Boolean(parsed?.armed);
            if (!armed) return false;

            window.localStorage.setItem(
                key,
                JSON.stringify({
                    ...parsed,
                    armed: false,
                    updatedAt: Date.now(),
                })
            );
            return true;
        } catch (_) {
            return false;
        }
    }, [getAiShotsAutoSwitchTicketKey]);

    useEffect(() => {
        if (!activeEpisode?.id) {
            setBatchAiShotsProgress(createBatchAiShotsProgressState());
            return;
        }
        const restored = loadBatchAiShotsRuntime(activeEpisode.id);
        if (restored) {
            setBatchAiShotsProgress(restored);
        } else {
            setBatchAiShotsProgress(createBatchAiShotsProgressState());
        }
    }, [activeEpisode?.id, loadBatchAiShotsRuntime]);

    useEffect(() => {
        if (!activeEpisode?.id) return;
        saveBatchAiShotsRuntime(activeEpisode.id, batchAiShotsProgress);
    }, [activeEpisode?.id, batchAiShotsProgress, saveBatchAiShotsRuntime]);

    useEffect(() => {
        batchAiShotsProgressRef.current = batchAiShotsProgress;
    }, [batchAiShotsProgress]);
    const normalizeOriginalScriptText = (value) => {
        const raw = typeof value === 'string' ? value.trim() : '';
        if (!raw) return '';
        if (/^\{\s*Original\s+Script\s+Text\s+for\s+Scene\s*\d+\s*\}$/i.test(raw)) return '';
        if (/^Original\s+Script\s+Text\s+for\s+Scene\s*\d+$/i.test(raw)) return '';
        return raw;
    };
    const sceneAutoSaveTimerRef = useRef(null);
    const sceneAutoSaveInFlightRef = useRef(false);
    const sceneAutoSaveQueuedRef = useRef(null);
    const sceneAutoSaveDraftRef = useRef(null);
    const sceneAutoSavedSnapshotRef = useRef({ sceneId: null, snapshot: '' });

    const buildSceneSavePayload = useCallback((scene) => {
        const toText = (value) => (value === null || value === undefined ? '' : String(value));
        return {
            scene_no: toText(scene?.scene_no),
            scene_name: toText(scene?.scene_name),
            equivalent_duration: toText(scene?.equivalent_duration),
            core_scene_info: toText(scene?.core_scene_info),
            original_script_text: normalizeOriginalScriptText(toText(scene?.original_script_text)),
            environment_name: toText(scene?.environment_name),
            linked_characters: toText(scene?.linked_characters),
            key_props: toText(scene?.key_props),
        };
    }, []);

    const buildSceneSnapshot = useCallback((scene) => JSON.stringify(buildSceneSavePayload(scene)), [buildSceneSavePayload]);

    const getSceneSelectionKey = (scene) => {
        if (scene?.id) return `id:${scene.id}`;
        return `draft:${scene?.scene_no || ''}|${scene?.scene_name || ''}|${scene?.environment_name || ''}|${scene?.original_script_text || ''}`;
    };

    const getSceneUpdatedAtMs = (scene) => {
        const candidate = scene?.updated_at || scene?.updatedAt || scene?.modified_at || scene?.modifiedAt || scene?.created_at || scene?.createdAt;
        if (!candidate) return 0;
        const parsed = Date.parse(candidate);
        return Number.isFinite(parsed) ? parsed : 0;
    };

    const getSceneOrderKey = (scene) => {
        const scenePart = String(scene?.scene_no || scene?.scene_id || scene?.id || '').trim();
        return scenePart;
    };

    const filteredScenes = useMemo(() => {
        const base = [...(scenes || [])];

        if (sceneSortMode === 'hierarchy') {
            base.sort((a, b) => {
                const ka = getSceneOrderKey(a);
                const kb = getSceneOrderKey(b);
                const cmp = ka.localeCompare(kb, undefined, { numeric: true, sensitivity: 'base' });
                if (cmp !== 0) return cmp;
                return String(a?.id || '').localeCompare(String(b?.id || ''), undefined, { numeric: true, sensitivity: 'base' });
            });
            if (sceneSortDirection === 'desc') base.reverse();
            return base;
        }

        base.sort((a, b) => {
            const ta = getSceneUpdatedAtMs(a);
            const tb = getSceneUpdatedAtMs(b);
            if (tb !== ta) return tb - ta;
            const ka = getSceneOrderKey(a);
            const kb = getSceneOrderKey(b);
            return ka.localeCompare(kb, undefined, { numeric: true, sensitivity: 'base' });
        });
        if (sceneSortDirection === 'asc') base.reverse();
        return base;
    }, [scenes, sceneSortMode, sceneSortDirection]);

    useEffect(() => {
        const validKeys = new Set((scenes || []).map(getSceneSelectionKey));
        setSelectedSceneKeys((prev) => prev.filter((key) => validKeys.has(key)));
    }, [scenes]);

    const selectedSceneKeySet = useMemo(() => new Set(selectedSceneKeys), [selectedSceneKeys]);
    const filteredSceneKeys = useMemo(() => (filteredScenes || []).map(getSceneSelectionKey), [filteredScenes]);
    const selectedFilteredCount = useMemo(
        () => filteredSceneKeys.filter((key) => selectedSceneKeySet.has(key)).length,
        [filteredSceneKeys, selectedSceneKeySet]
    );
    const allFilteredSelected = filteredSceneKeys.length > 0 && selectedFilteredCount === filteredSceneKeys.length;

    const toggleSceneSelected = (scene) => {
        const key = getSceneSelectionKey(scene);
        setSelectedSceneKeys((prev) => (
            prev.includes(key)
                ? prev.filter((k) => k !== key)
                : [...prev, key]
        ));
    };

    const toggleSelectAllFiltered = () => {
        if (!filteredSceneKeys.length) return;
        setSelectedSceneKeys((prev) => {
            const prevSet = new Set(prev);
            if (allFilteredSelected) {
                return prev.filter((key) => !filteredSceneKeys.includes(key));
            }
            filteredSceneKeys.forEach((key) => prevSet.add(key));
            return Array.from(prevSet);
        });
    };

    const getStagingShotField = (shot, field) => {
        if (!shot) return '';
        const map = {
            shot_id: ['Shot ID', 'shot_id'],
            shot_name: ['Shot Name', 'shot_name'],
            scene_id: ['Scene ID', 'scene_id'],
            start_frame: ['Start Frame', 'start_frame'],
            start_frame_cn: ['Start Frame (CN)', 'start_frame_cn', '起始帧（中文）'],
            video_content: ['Video Content', 'video_content'],
            video_content_cn: ['Video Content (CN)', 'video_content_cn', 'video_prompt_cn', '视频内容（中文）'],
            duration: ['Duration (s)', 'duration'],
            end_frame: ['End Frame', 'end_frame'],
            end_frame_cn: ['End Frame (CN)', 'end_frame_cn', '结束帧（中文）'],
            associated_entities: ['Associated Entities', 'associated_entities'],
            shot_logic_cn: ['Shot Logic (CN)', 'shot_logic_cn'],
            keyframes: ['Keyframes', 'keyframes'],
            keyframes_cn: ['Keyframes (CN)', 'keyframes_cn', '关键帧（中文）'],
        };
        const keys = map[field] || [];
        for (const key of keys) {
            const value = shot[key];
            if (value !== undefined && value !== null) return String(value);
        }
        return '';
    };

    const DEFAULT_AI_SHOT_STAGING_COLUMNS = [
        'Shot ID',
        'Shot Name',
        'Scene ID',
        'Shot Logic (CN)',
        'Start Frame',
        'Video Content',
        'Duration (s)',
        'Keyframes',
        'End Frame',
        'Start Frame (CN)',
        'Video Content (CN)',
        'Keyframes (CN)',
        'End Frame (CN)',
        'Associated Entities',
    ];

    const getAiShotColumnLabel = (columnKey) => {
        const key = String(columnKey || '');
        const map = {
            shot_id: 'Shot ID',
            shot_name: 'Shot Name',
            scene_id: 'Scene ID',
            shot_logic_cn: 'Shot Logic (CN)',
            start_frame: 'Start Frame',
            video_content: 'Video Content',
            duration: 'Duration (s)',
            keyframes: 'Keyframes',
            end_frame: 'End Frame',
            start_frame_cn: 'Start Frame (CN)',
            video_content_cn: 'Video Content (CN)',
            video_prompt_cn: 'Video Content (CN)',
            keyframes_cn: 'Keyframes (CN)',
            end_frame_cn: 'End Frame (CN)',
            associated_entities: 'Associated Entities',
            prompt_cn: 'Prompt (CN) [Legacy]',
        };
        return map[key] || key;
    };

    const isAiShotLongTextColumn = (columnKey) => {
        const n = String(columnKey || '').toLowerCase();
        return (
            n.includes('start frame') ||
            n.includes('end frame') ||
            n.includes('video content') ||
            n.includes('keyframe') ||
            n.includes('prompt') ||
            n.includes('logic') ||
            n.includes('entities') ||
            n.includes('start_frame') ||
            n.includes('end_frame') ||
            n.includes('video_content') ||
            n.includes('shot_logic') ||
            n.includes('associated_entities')
        );
    };

    const getAiShotColumnValue = (shot, columnKey) => {
        if (!shot) return '';
        if (shot[columnKey] !== undefined && shot[columnKey] !== null) return String(shot[columnKey]);

        const normalized = String(columnKey || '').toLowerCase();
        if (normalized === 'shot id') return getStagingShotField(shot, 'shot_id');
        if (normalized === 'shot name') return getStagingShotField(shot, 'shot_name');
        if (normalized === 'scene id') return getStagingShotField(shot, 'scene_id');
        if (normalized === 'shot logic (cn)') return getStagingShotField(shot, 'shot_logic_cn');
        if (normalized === 'start frame') return getStagingShotField(shot, 'start_frame');
        if (normalized === 'video content') return getStagingShotField(shot, 'video_content');
        if (normalized === 'duration (s)') return getStagingShotField(shot, 'duration');
        if (normalized === 'keyframes') return getStagingShotField(shot, 'keyframes');
        if (normalized === 'end frame') return getStagingShotField(shot, 'end_frame');
        if (normalized === 'start frame (cn)') return getStagingShotField(shot, 'start_frame_cn');
        if (normalized === 'video content (cn)') return getStagingShotField(shot, 'video_content_cn');
        if (normalized === 'keyframes (cn)') return getStagingShotField(shot, 'keyframes_cn');
        if (normalized === 'end frame (cn)') return getStagingShotField(shot, 'end_frame_cn');
        if (normalized === 'associated entities') return getStagingShotField(shot, 'associated_entities');
        if (normalized === 'prompt (cn)') return String(shot['Prompt (CN)'] || shot.prompt_cn || '');
        return '';
    };

    const splitCombinedCnPrompt = (raw) => {
        const textValue = String(raw || '').trim();
        if (!textValue) {
            return {
                start_frame_cn: '',
                video_prompt_cn: '',
                keyframes_cn: '',
                end_frame_cn: '',
            };
        }

        const lines = textValue
            .split(/\n|<br\s*\/?>/i)
            .map((line) => String(line || '').trim())
            .filter(Boolean);

        let start = '';
        let video = '';
        let keyframes = '';
        let end = '';

        lines.forEach((line) => {
            const lower = line.toLowerCase();
            if (/^(start\s*frame\s*(cn)?\s*:|start\s*:|起始帧\s*[:：])/.test(lower) || /^起始帧\s*[:：]/.test(line)) {
                start = line.replace(/^(start\s*frame\s*(cn)?\s*:|start\s*:|起始帧\s*[:：])/i, '').trim();
                return;
            }
            if (/^(video\s*(cn)?\s*:|视频提示词\s*[:：]|视频\s*[:：])/.test(lower) || /^视频(提示词)?\s*[:：]/.test(line)) {
                video = line.replace(/^(video\s*(cn)?\s*:|视频提示词\s*[:：]|视频\s*[:：])/i, '').trim();
                return;
            }
            if (/^(key\s*frames?\s*(cn)?\s*:|关键帧\s*[:：])/.test(lower) || /^关键帧\s*[:：]/.test(line)) {
                keyframes = line.replace(/^(key\s*frames?\s*(cn)?\s*:|关键帧\s*[:：])/i, '').trim();
                return;
            }
            if (/^(end\s*frame\s*(cn)?\s*:|end\s*:|收尾帧\s*[:：]|结束帧\s*[:：])/.test(lower) || /^(收尾帧|结束帧)\s*[:：]/.test(line)) {
                end = line.replace(/^(end\s*frame\s*(cn)?\s*:|end\s*:|收尾帧\s*[:：]|结束帧\s*[:：])/i, '').trim();
            }
        });

        if (!start && !video && !keyframes && !end) {
            return {
                start_frame_cn: textValue,
                video_prompt_cn: textValue,
                keyframes_cn: textValue,
                end_frame_cn: textValue,
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

    const extractShotRegenMarker = (rawLogic) => {
        const textValue = String(rawLogic || '').trim();
        if (!textValue) return { mode: null, cleanLogic: '' };
        if (/=更新分镜\s*$/.test(textValue)) {
            return {
                mode: 'update',
                cleanLogic: textValue.replace(/\s*=更新分镜\s*$/, '').trim(),
            };
        }
        if (/=补充分镜\s*$/.test(textValue)) {
            return {
                mode: 'add',
                cleanLogic: textValue.replace(/\s*=补充分镜\s*$/, '').trim(),
            };
        }
        return { mode: null, cleanLogic: textValue };
    };

    const buildCanonicalAiStagingRow = (shot, fallbackSceneCode = '') => {
        const base = {
            'Shot ID': getStagingShotField(shot, 'shot_id'),
            'Shot Name': getStagingShotField(shot, 'shot_name'),
            'Scene ID': getStagingShotField(shot, 'scene_id') || String(fallbackSceneCode || ''),
            'Shot Logic (CN)': getStagingShotField(shot, 'shot_logic_cn'),
            'Start Frame': getStagingShotField(shot, 'start_frame'),
            'Video Content': getStagingShotField(shot, 'video_content'),
            'Duration (s)': getStagingShotField(shot, 'duration'),
            'Keyframes': getStagingShotField(shot, 'keyframes'),
            'End Frame': getStagingShotField(shot, 'end_frame'),
            'Start Frame (CN)': getStagingShotField(shot, 'start_frame_cn'),
            'Video Content (CN)': getStagingShotField(shot, 'video_content_cn'),
            'Keyframes (CN)': getStagingShotField(shot, 'keyframes_cn'),
            'End Frame (CN)': getStagingShotField(shot, 'end_frame_cn'),
            'Associated Entities': getStagingShotField(shot, 'associated_entities'),
        };

        Object.keys(shot || {}).forEach((key) => {
            if (base[key] !== undefined) return;
            const value = shot?.[key];
            if (value === undefined || value === null || String(value).trim() === '') return;
            base[key] = String(value);
        });

        return base;
    };

    const sortAiStagingRows = (rows) => {
        return [...(Array.isArray(rows) ? rows : [])].sort((left, right) => {
            const leftId = String(getStagingShotField(left, 'shot_id') || '').trim();
            const rightId = String(getStagingShotField(right, 'shot_id') || '').trim();
            return leftId.localeCompare(rightId, undefined, { numeric: true, sensitivity: 'base' });
        });
    };

    const buildShotWritePayloadFromRow = (shot, options = {}) => {
        const fallbackSceneCode = String(options?.fallbackSceneCode || '').trim();
        const existingTechnicalNotes = String(options?.existingTechnicalNotes || '').trim();
        const promptCnRaw = String(shot?.['Prompt (CN)'] || shot?.prompt_cn || '').trim();
        const startFrameCnRaw = getStagingShotField(shot, 'start_frame_cn');
        const videoPromptCnRaw = getStagingShotField(shot, 'video_content_cn');
        const keyframesCnRaw = getStagingShotField(shot, 'keyframes_cn');
        const endFrameCnRaw = getStagingShotField(shot, 'end_frame_cn');
        const combinedFallback = splitCombinedCnPrompt(promptCnRaw);

        let technicalNotesObj = {};
        if (existingTechnicalNotes) {
            try {
                const parsed = JSON.parse(existingTechnicalNotes);
                if (parsed && typeof parsed === 'object') technicalNotesObj = parsed;
            } catch (_) {
                technicalNotesObj = {};
            }
        }

        const finalStartCn = startFrameCnRaw || combinedFallback.start_frame_cn;
        const finalVideoCn = videoPromptCnRaw || combinedFallback.video_prompt_cn;
        const finalKeyframesCn = keyframesCnRaw || combinedFallback.keyframes_cn;
        const finalEndCn = endFrameCnRaw || combinedFallback.end_frame_cn;

        if (finalStartCn) technicalNotesObj.start_frame_cn = finalStartCn;
        if (finalVideoCn) technicalNotesObj.video_prompt_cn = finalVideoCn;
        if (finalKeyframesCn) technicalNotesObj.keyframes_cn = finalKeyframesCn;
        if (finalEndCn) technicalNotesObj.end_frame_cn = finalEndCn;

        if (finalStartCn || finalVideoCn || finalKeyframesCn || finalEndCn) {
            technicalNotesObj.shot_prompt_cn = [
                `起始帧：${finalStartCn || ''}`,
                `视频：${finalVideoCn || ''}`,
                `关键帧：${finalKeyframesCn || ''}`,
                `收尾帧：${finalEndCn || ''}`,
            ].join('<br>');
        }

        return {
            shot_id: getStagingShotField(shot, 'shot_id'),
            shot_name: getStagingShotField(shot, 'shot_name'),
            scene_code: getStagingShotField(shot, 'scene_id') || fallbackSceneCode,
            start_frame: getStagingShotField(shot, 'start_frame'),
            end_frame: getStagingShotField(shot, 'end_frame'),
            video_content: getStagingShotField(shot, 'video_content'),
            duration: getStagingShotField(shot, 'duration'),
            associated_entities: getStagingShotField(shot, 'associated_entities'),
            shot_logic_cn: getStagingShotField(shot, 'shot_logic_cn'),
            keyframes: getStagingShotField(shot, 'keyframes'),
            technical_notes: Object.keys(technicalNotesObj).length > 0 ? JSON.stringify(technicalNotesObj) : existingTechnicalNotes || '',
        };
    };

    const hasAiShotRegenMarkers = useMemo(() => {
        return (Array.isArray(aiShotsStaging?.content) ? aiShotsStaging.content : []).some((row) => {
            const marker = extractShotRegenMarker(getStagingShotField(row, 'shot_logic_cn'));
            return marker.mode === 'update' || marker.mode === 'add';
        });
    }, [aiShotsStaging?.content]);

    const buildShotSupplementImportSummaryLines = (report) => {
        if (!report || typeof report !== 'object') return [];
        const lines = [];
        lines.push(t(
            `更新 ${Number(report.updated_count || 0)} 条，新增 ${Number(report.created_count || 0)} 条，跳过 ${Number(report.skipped_count || 0)} 条。`,
            `Updated ${Number(report.updated_count || 0)}, created ${Number(report.created_count || 0)}, skipped ${Number(report.skipped_count || 0)}.`
        ));
        const skipReasons = Array.isArray(report.skipped_items)
            ? Array.from(new Set(report.skipped_items.map((item) => String(item?.reason || '').trim()).filter(Boolean)))
            : [];
        if (skipReasons.length > 0) {
            lines.push(t(`跳过原因：${skipReasons.join('；')}`, `Skipped because: ${skipReasons.join('; ')}`));
        }
        return lines;
    };

    const openShotRegenModal = () => {
        if (!editingScene?.id) return;
        if (!Array.isArray(aiShotsStaging?.content) || aiShotsStaging.content.length === 0) {
            alert(t('请先准备当前场景的 AI 镜头暂存内容，再执行补充分镜。', 'Prepare staged AI shots for this scene before running shot supplement.'));
            return;
        }
        setShotRegenModal({
            open: true,
            sceneId: editingScene.id,
            instructions: '',
            submitting: false,
            error: '',
        });
    };

    const handleOpenShotSupplementMenu = async (scene) => {
        const sceneId = Number(scene?.id || 0);
        if (!sceneId) return;
        setPendingShotSupplementSceneId(sceneId);
        setEditingScene(scene);
    };

    const applySelectiveAiShotDiff = async (sceneId, rows) => {
        const stagedRows = Array.isArray(rows) ? rows : [];
        if (!stagedRows.length) {
            throw new Error('No staged shot rows available for selective apply');
        }

        const existingShots = await fetchShots(sceneId);
        const shotByDisplayId = new Map();
        (Array.isArray(existingShots) ? existingShots : []).forEach((shot) => {
            const key = String(shot?.shot_id || '').trim().toUpperCase();
            if (!key) return;
            shotByDisplayId.set(key, shot);
        });

        const fallbackSceneCode = String(
            editingScene?.scene_code || editingScene?.scene_no || editingScene?.scene_id || ''
        ).trim();

        let updatedCount = 0;
        let createdCount = 0;
        let skippedCount = 0;
        const updatedItems = [];
        const createdItems = [];
        const skippedItems = [];
        const errors = [];

        for (const row of stagedRows) {
            const shotId = String(getStagingShotField(row, 'shot_id') || '').trim();
            const shotLogic = getStagingShotField(row, 'shot_logic_cn');
            const { mode, cleanLogic } = extractShotRegenMarker(shotLogic);
            if (!mode) {
                skippedCount += 1;
                skippedItems.push({
                    shot_id: shotId || t('未命名', 'Unnamed'),
                    shot_name: String(getStagingShotField(row, 'shot_name') || '').trim(),
                    reason: t('未带补充分镜 marker', 'Missing shot supplement marker'),
                });
                continue;
            }
            if (!shotId) {
                errors.push(t('存在缺少 Shot ID 的补充分镜行。', 'A shot supplement row is missing Shot ID.'));
                continue;
            }

            const normalizedId = shotId.toUpperCase();
            if (mode === 'update') {
                const existingShot = shotByDisplayId.get(normalizedId);
                if (!existingShot) {
                    errors.push(t(`未找到待更新镜头: ${shotId}`, `Target shot for update was not found: ${shotId}`));
                    continue;
                }

                const payload = buildShotWritePayloadFromRow(row, {
                    fallbackSceneCode,
                    existingTechnicalNotes: existingShot?.technical_notes || '',
                });
                payload.shot_logic_cn = cleanLogic || payload.shot_logic_cn;
                await updateShot(existingShot.id, payload);
                updatedCount += 1;
                updatedItems.push({
                    shot_id: shotId,
                    shot_name: String(payload.shot_name || existingShot?.shot_name || '').trim(),
                    reason: t('按 =更新分镜 更新既有镜头', 'Updated existing shot via =更新分镜'),
                });
                shotByDisplayId.set(normalizedId, { ...existingShot, ...payload });
                continue;
            }

            if (shotByDisplayId.has(normalizedId)) {
                errors.push(t(`新增镜头 ID 已存在: ${shotId}`, `Add-shot ID already exists: ${shotId}`));
                continue;
            }

            const payload = buildShotWritePayloadFromRow(row, {
                fallbackSceneCode,
                existingTechnicalNotes: '',
            });
            payload.shot_logic_cn = cleanLogic || payload.shot_logic_cn;
            const created = await createShot(sceneId, payload);
            createdCount += 1;
            createdItems.push({
                shot_id: shotId,
                shot_name: String(payload.shot_name || created?.shot_name || '').trim(),
                reason: t('按 =补充分镜 新增镜头', 'Created new shot via =补充分镜'),
            });
            shotByDisplayId.set(normalizedId, created);
        }

        if (errors.length > 0) {
            const detail = errors.slice(0, 5).join('\n');
            throw new Error(errors.length > 5 ? `${detail}\n...` : detail);
        }

        return {
            updatedCount,
            createdCount,
            skippedCount,
            updatedItems,
            createdItems,
            skippedItems,
        };
    };

    const handleConfirmShotRegenerate = async () => {
        const sceneId = shotRegenModal.sceneId || editingScene?.id;
        if (!sceneId) return;

        setShotRegenModal((prev) => ({ ...prev, submitting: true, error: '' }));
        setAiShotsFlowStatus({
            phase: 'generating',
            sceneId,
            message: t('正在补充分镜...', 'Generating shot supplement...'),
        });

        try {
            const result = await regenerateSceneShots(sceneId, {
                content: aiShotsStaging.content || [],
                additional_instructions: String(shotRegenModal.instructions || '').trim(),
            });

            const nextRows = Array.isArray(result?.content) ? result.content : [];
            if (!nextRows.length) {
                throw new Error(t('补充分镜返回空结果。', 'Shot supplement returned empty result.'));
            }

            setAiShotsStaging((prev) => ({
                ...prev,
                sceneId,
                content: nextRows,
                rawText: result?.raw_text || '',
                usage: result?.usage || null,
                timestamp: result?.timestamp || null,
                warnings: Array.isArray(result?.warnings) ? result.warnings : [],
                error: null,
            }));
            setShotSupplementImportReport(null);
            setAiShotsFlowStatus({
                phase: 'importing',
                sceneId,
                message: t('补充分镜已生成，正在自动导入到场景...', 'Shot supplement generated. Importing to scene...'),
            });

            const summary = await applySelectiveAiShotDiff(sceneId, nextRows);
            const nextReport = {
                scene_id: sceneId,
                updated_count: summary.updatedCount,
                created_count: summary.createdCount,
                skipped_count: summary.skippedCount,
                updated_items: summary.updatedItems,
                created_items: summary.createdItems,
                skipped_items: summary.skippedItems,
            };
            nextReport.summary_lines = buildShotSupplementImportSummaryLines(nextReport);
            setShotSupplementImportReport(nextReport);
            setShotRegenModal({ open: false, sceneId: null, instructions: '', submitting: false, error: '' });
            setAiShotsFlowStatus({
                phase: 'completed',
                sceneId,
                message: t(
                    `补充分镜已自动导入：更新 ${summary.updatedCount} 条，新增 ${summary.createdCount} 条，跳过 ${summary.skippedCount} 条。`,
                    `Shot supplement auto-imported: ${summary.updatedCount} updated, ${summary.createdCount} created, ${summary.skippedCount} skipped.`
                ),
            });
            onLog?.(
                t(
                    `补充分镜已自动导入：更新 ${summary.updatedCount} 条，新增 ${summary.createdCount} 条，跳过 ${summary.skippedCount} 条。`,
                    `Shot supplement auto-imported: ${summary.updatedCount} updated, ${summary.createdCount} created, ${summary.skippedCount} skipped.`
                ),
                'success'
            );
            alert(
                t(
                    `补充分镜自动导入完成\n更新: ${summary.updatedCount}\n新增: ${summary.createdCount}\n跳过: ${summary.skippedCount}`,
                    `Shot supplement auto-import completed\nUpdated: ${summary.updatedCount}\nCreated: ${summary.createdCount}\nSkipped: ${summary.skippedCount}`
                )
            );
            if (typeof refreshShots === 'function') {
                await refreshShots();
            }
        } catch (e) {
            const message = e?.response?.data?.detail || e?.message || 'Shot supplement failed';
            console.error('[SceneManager] shot supplement failed', e);
            setShotRegenModal((prev) => ({ ...prev, submitting: false, error: message }));
            setAiShotsFlowStatus({
                phase: 'failed',
                sceneId,
                message: t(`补充分镜失败：${message}`, `Shot supplement failed: ${message}`),
            });
            onLog?.(t('补充分镜失败: ', 'Shot supplement failed: ') + message, 'error');
        }
    };

    const handleApplyAiShotsStaging = async () => {
        if (!editingScene?.id) return;

        setAiShotsStaging((prev) => ({ ...prev, applying: true }));
        try {
            if (hasAiShotRegenMarkers) {
                if (!await confirmUiMessage(t('应用这些补充分镜吗？只会更新带 =更新分镜 的镜头，并新增带 =补充分镜 的镜头。', 'Apply this shot supplement? Only rows marked =更新分镜 will update existing shots, and rows marked =补充分镜 will be created.'))) {
                    return;
                }
                const summary = await applySelectiveAiShotDiff(editingScene.id, aiShotsStaging.content || []);
                const nextReport = {
                    scene_id: editingScene.id,
                    updated_count: summary.updatedCount,
                    created_count: summary.createdCount,
                    skipped_count: summary.skippedCount,
                    updated_items: summary.updatedItems,
                    created_items: summary.createdItems,
                    skipped_items: summary.skippedItems,
                };
                nextReport.summary_lines = buildShotSupplementImportSummaryLines(nextReport);
                setShotSupplementImportReport(nextReport);
                onLog?.(
                    t(
                        `补充分镜已导入：更新 ${summary.updatedCount} 条，新增 ${summary.createdCount} 条，跳过 ${summary.skippedCount} 条。`,
                        `Shot supplement imported: ${summary.updatedCount} updated, ${summary.createdCount} created, ${summary.skippedCount} skipped.`
                    ),
                    'success'
                );
                alert(
                    t(
                        `补充分镜导入完成\n更新: ${summary.updatedCount}\n新增: ${summary.createdCount}\n跳过: ${summary.skippedCount}`,
                        `Shot supplement import completed\nUpdated: ${summary.updatedCount}\nCreated: ${summary.createdCount}\nSkipped: ${summary.skippedCount}`
                    )
                );
            } else {
                if (!await confirmUiMessage(t('应用这些镜头吗？这会替换现有镜头。', 'Apply these shots? This will replace existing shots.'))) {
                    return;
                }
                setShotSupplementImportReport(null);
                await applySceneAIResult(editingScene.id, { content: aiShotsStaging.content || [] });
                onLog?.(t('镜头已应用到数据库。', 'Shots applied to database.'), 'success');
            }

            if (typeof refreshShots === 'function') {
                await refreshShots();
            }
        } catch (e) {
            onLog?.(t('应用镜头失败: ', 'Failed to apply shots: ') + (e?.response?.data?.detail || e?.message), 'error');
        } finally {
            setAiShotsStaging((prev) => ({ ...prev, applying: false }));
        }
    };

    const aiShotsStagingColumns = useMemo(() => {
        const rows = Array.isArray(aiShotsStaging?.content) ? aiShotsStaging.content : [];
        const discovered = [];
        const seen = new Set();

        for (const row of rows) {
            if (!row || typeof row !== 'object') continue;
            for (const key of Object.keys(row)) {
                const stableKey = String(key || '').trim();
                if (!stableKey || seen.has(stableKey)) continue;
                seen.add(stableKey);
                discovered.push(stableKey);
            }
        }

        if (discovered.length === 0) return [...DEFAULT_AI_SHOT_STAGING_COLUMNS];

        const ordered = DEFAULT_AI_SHOT_STAGING_COLUMNS.filter((k) => seen.has(k));
        for (const key of discovered) {
            if (!ordered.includes(key)) ordered.push(key);
        }
        return ordered;
    }, [aiShotsStaging?.content]);

    const openAiShotRowEditor = (shot, idx) => {
        setAiShotRowEditor({
            open: true,
            index: idx,
            data: {
                shot_id: getStagingShotField(shot, 'shot_id'),
                shot_name: getStagingShotField(shot, 'shot_name'),
                scene_id: getStagingShotField(shot, 'scene_id'),
                start_frame: getStagingShotField(shot, 'start_frame'),
                start_frame_cn: getStagingShotField(shot, 'start_frame_cn'),
                video_content: getStagingShotField(shot, 'video_content'),
                video_content_cn: getStagingShotField(shot, 'video_content_cn'),
                duration: getStagingShotField(shot, 'duration'),
                end_frame: getStagingShotField(shot, 'end_frame'),
                end_frame_cn: getStagingShotField(shot, 'end_frame_cn'),
                associated_entities: getStagingShotField(shot, 'associated_entities'),
                shot_logic_cn: getStagingShotField(shot, 'shot_logic_cn'),
                keyframes: getStagingShotField(shot, 'keyframes'),
                keyframes_cn: getStagingShotField(shot, 'keyframes_cn'),
            },
        });
    };

    const saveAiShotRowEditor = () => {
        if (!aiShotRowEditor.open || aiShotRowEditor.index < 0) return;
        const currentRows = [...(aiShotsStaging.content || [])];
        const current = currentRows[aiShotRowEditor.index] || {};
        const edited = aiShotRowEditor.data || {};

        currentRows[aiShotRowEditor.index] = {
            ...current,
            'Shot ID': edited.shot_id || '',
            'Shot Name': edited.shot_name || '',
            'Scene ID': edited.scene_id || '',
            'Start Frame': edited.start_frame || '',
            'Start Frame (CN)': edited.start_frame_cn || '',
            'Video Content': edited.video_content || '',
            'Video Content (CN)': edited.video_content_cn || '',
            'Duration (s)': edited.duration || '',
            'End Frame': edited.end_frame || '',
            'End Frame (CN)': edited.end_frame_cn || '',
            'Associated Entities': edited.associated_entities || '',
            'Shot Logic (CN)': edited.shot_logic_cn || '',
            'Keyframes': edited.keyframes || '',
            'Keyframes (CN)': edited.keyframes_cn || '',
        };

        setAiShotsStaging(prev => ({ ...prev, content: currentRows }));
        setAiShotRowEditor({ open: false, index: -1, data: null });
    };

    useEffect(() => {
        fetchMe().then((user) => {
            setIsSuperuser(!!user?.is_superuser);
        }).catch(() => {
            setIsSuperuser(false);
        });
    }, []);

    const parseScenesFromText = useCallback((text) => {
        if (!text) return [];
        const lines = text.split('\n').filter(l => l.trim().includes('|'));
        const headerIdx = lines.findIndex(l =>
            (l.includes("Scene No") || l.includes("场次序号") || l.includes("Scene ID") || l.includes("场次") || l.includes("Title"))
        );

        if (headerIdx === -1) return [];

        const headerLine = lines[headerIdx];
        let headers = headerLine.split('|').map(c => c.trim());
        if (headers.length > 0 && headers[0] === "") headers.shift();
        if (headers.length > 0 && headers[headers.length - 1] === "") headers.pop();

        const normalizeHeader = (h) => h.toLowerCase().replace(/[\.\s]/g, '');
        const headerMap = {};
        headers.forEach((h, idx) => {
            const n = normalizeHeader(h);
            if (n.includes("episodeid") || n.includes("集id")) headerMap['episode_id'] = idx;
            else if ((n.includes("sceneid") && !n.includes("sceneno")) || n.includes("场景id")) headerMap['scene_id'] = idx;
            if (n.includes("sceneno") || n.includes("场次")) headerMap['scene_no'] = idx;
            else if (n.includes("scenename") || n.includes("title")) headerMap['scene_name'] = idx;
            else if (n.includes("equivalentduration")) headerMap['equivalent_duration'] = idx;
            else if (n.includes("coresceneinfo") || n.includes("coregoal")) headerMap['core_scene_info'] = idx;
            else if (n.includes("originalscripttext") || n.includes("description")) headerMap['original_script_text'] = idx;
            else if (n.includes("environmentname") || n.includes("environment")) headerMap['environment_name'] = idx;
            else if (n.includes("environmentrelation")) headerMap['environment_relation'] = idx;
            else if (n.includes("entrystate")) headerMap['entry_state'] = idx;
            else if (n.includes("exitstate")) headerMap['exit_state'] = idx;
            else if (n.includes("linkedcharacters")) headerMap['linked_characters'] = idx;
            else if (n.includes("keyprops")) headerMap['key_props'] = idx;
        });

        const rows = [];
        let inShotTable = false;

        for (let i = headerIdx + 1; i < lines.length; i++) {
            const line = lines[i];
            if (line.includes("Shot ID") || line.includes("镜头ID")) {
                inShotTable = true;
                continue;
            }
            if (line.includes("Scene No") || line.includes("场次序号")) {
                inShotTable = false;
                continue;
            }
            if (inShotTable) continue;
            if (line.includes('---')) continue;

            let cols = line.split('|').map(c => c.trim());
            if (cols.length > 0 && cols[0] === "") cols.shift();
            if (cols.length > 0 && cols[cols.length - 1] === "") cols.pop();

            if (cols.length >= 2) {
                const cleanCol = (txt) => txt ? txt.replace(/<br\s*\/?>/gi, '\n').replace(/\\\|/g, '|') : '';
                const getVal = (key, fallbackIdx) => {
                    const idx = headerMap[key] !== undefined ? headerMap[key] : fallbackIdx;
                    return cols[idx] ? cleanCol(cols[idx]) : '';
                };

                const isNewFormat = cols.length >= 13 || headerMap['episode_id'] !== undefined || headerMap['scene_id'] !== undefined;
                const fallback = isNewFormat
                    ? {
                        scene_no: 2,
                        scene_name: 3,
                        equivalent_duration: 4,
                        core_scene_info: 5,
                        original_script_text: 6,
                        environment_name: 7,
                        linked_characters: 11,
                        key_props: 12,
                    }
                    : {
                        scene_no: 0,
                        scene_name: 1,
                        equivalent_duration: 2,
                        core_scene_info: 3,
                        original_script_text: 4,
                        environment_name: 5,
                        linked_characters: 6,
                        key_props: 7,
                    };

                rows.push({
                    scene_no: getVal('scene_no', fallback.scene_no),
                    scene_name: getVal('scene_name', fallback.scene_name),
                    equivalent_duration: getVal('equivalent_duration', fallback.equivalent_duration),
                    core_scene_info: getVal('core_scene_info', fallback.core_scene_info),
                    original_script_text: normalizeOriginalScriptText(getVal('original_script_text', fallback.original_script_text)),
                    environment_name: getVal('environment_name', fallback.environment_name),
                    linked_characters: getVal('linked_characters', fallback.linked_characters),
                    key_props: getVal('key_props', fallback.key_props)
                });
            }
        }
        return rows;
    }, []);

    // Fetch Entities (Environment) for image matching
    useEffect(() => {

        const loadScenes = async () => {
             if (activeEpisode?.id) {
                 setSceneListLoading(true);
                 const quickPreview = parseScenesFromText(activeEpisode?.scene_content);
                 setScenes(quickPreview);
                 try {
                     const dbScenes = await fetchScenes(activeEpisode.id);
                     if (dbScenes && dbScenes.length > 0) {
                         // Check for incomplete data (Schema Update Backfill)
                         const inContent = activeEpisode.scene_content;
                         if (inContent && dbScenes.some(s => !s.linked_characters && !s.key_props)) {
                             const parsed = parseScenesFromText(inContent);
                             if (parsed.length > 0) {
                                 const merged = dbScenes.map(dbS => {
                                     // Match by Scene Number
                                     const match = parsed.find(p => p.scene_no === dbS.scene_no);
                                     if (match) {
                                         const dbOriginalScriptText = normalizeOriginalScriptText(dbS.original_script_text);
                                         const matchOriginalScriptText = normalizeOriginalScriptText(match.original_script_text);
                                         return {
                                             ...dbS,
                                             linked_characters: dbS.linked_characters || match.linked_characters,
                                             key_props: dbS.key_props || match.key_props,
                                             environment_name: dbS.environment_name || match.environment_name,
                                             core_scene_info: dbS.core_scene_info || match.core_scene_info,
                                             original_script_text: dbOriginalScriptText || matchOriginalScriptText
                                         };
                                     }
                                     return dbS;
                                 });
                                 setScenes(merged);
                                 return;
                             }
                         }
                         setScenes((dbScenes || []).map((scene) => ({
                             ...scene,
                             original_script_text: normalizeOriginalScriptText(scene?.original_script_text),
                         })));
                     } else {
                         // Only parse if DB is empty
                         setScenes(parseScenesFromText(activeEpisode?.scene_content));
                     }
                 } catch(e) {
                     console.error("Failed to load scenes from DB", e);
                     const parsedFallback = parseScenesFromText(activeEpisode?.scene_content);
                     setScenes(parsedFallback);
                 } finally {
                     setSceneListLoading(false);
                 }
             } else {
                 setSceneListLoading(false);
             }
        };

        if (projectId) fetchEntities(projectId).then(setEntities).catch(console.error);
        loadScenes();
    }, [activeEpisode, projectId, parseScenesFromText]);

    useEffect(() => {
        if (!activeEpisode?.id) {
            setSceneShotCountMap({});
            return;
        }
        if (batchAiShotsProgress.running) return;
        refreshSceneShotCounts();
    }, [
        activeEpisode?.id,
        sceneIdSignature,
        aiShotsFlowStatus.phase,
        batchAiShotsProgress.running,
        batchAiShotsProgress.total,
        refreshSceneShotCounts,
    ]);

    const sceneSubjectGapMap = useMemo(() => {
        const entityPool = mergeEntityPoolWithSubjectIndex(entities, activeEpisode?.ai_scene_analysis_result || '');
        const next = new Map();
        for (const scene of (Array.isArray(scenes) ? scenes : [])) {
            const missing = findMissingSceneSubjectRefs(scene, entityPool);
            if (missing.length === 0) continue;
            const key = getSceneSubjectStatusKey(scene);
            next.set(key, {
                missing,
                byType: {
                    character: missing.filter((item) => item.type === 'character').length,
                    prop: missing.filter((item) => item.type === 'prop').length,
                    environment: missing.filter((item) => item.type === 'environment').length,
                },
            });
        }
        return next;
    }, [activeEpisode?.ai_scene_analysis_result, entities, scenes]);

    async function handleSupplementSceneSubjects(sceneCandidate, gapReport = null, options = {}) {
        const stableScene = sceneCandidate && typeof sceneCandidate === 'object' ? sceneCandidate : null;
        if (!stableScene || !projectId) return null;

        const stableGap = (gapReport && typeof gapReport === 'object')
            ? gapReport
            : { missing: findMissingSceneSubjectRefs(stableScene, mergeEntityPoolWithSubjectIndex(entities, activeEpisode?.ai_scene_analysis_result || '')) };
        const missing = Array.isArray(stableGap?.missing) ? stableGap.missing : [];
        if (missing.length === 0) return {
            createdItems: [],
            skippedItems: [],
            failedItems: [],
            sceneReports: [],
            countsByType: { character: 0, prop: 0, environment: 0 },
        };

        const silent = Boolean(options?.silent);
        const sceneLabel = String(stableScene?.scene_no || stableScene?.scene_name || stableScene?.id || '').trim() || '#unknown';
        if (!silent) {
            const confirmed = await confirmUiMessage(
                t(
                    `检测到场景 ${sceneLabel} 缺失 ${missing.length} 个 subjects，是否立即补齐到 Subjects 资产库？`,
                    `Scene ${sceneLabel} is missing ${missing.length} subjects. Add them to the Subjects library now?`
                )
            );
            if (!confirmed) return null;
        }

        const statusKey = getSceneSubjectStatusKey(stableScene);
        setSceneSubjectSupplementingMap((prev) => ({ ...prev, [statusKey]: true }));
        try {
            const latestEntities = await fetchEntities(projectId).catch(() => (Array.isArray(entities) ? entities : []));
            const latestEntityPool = mergeEntityPoolWithSubjectIndex(latestEntities, activeEpisode?.ai_scene_analysis_result || '');
            const report = await createMissingSceneSubjectPlaceholders({
                projectId,
                sceneRows: [stableScene],
                existingEntities: latestEntityPool,
                onLog,
            });

            const refreshed = await fetchEntities(projectId).catch(() => report.entities || latestEntities || []);
            setEntities(Array.isArray(refreshed) ? refreshed : []);

            const createdCount = Array.isArray(report?.createdItems) ? report.createdItems.length : 0;
            const skippedCount = Array.isArray(report?.skippedItems) ? report.skippedItems.length : 0;
            const failedCount = Array.isArray(report?.failedItems) ? report.failedItems.length : 0;
            if (createdCount > 0) {
                onLog?.(
                    t(
                        `场景 ${sceneLabel} 已补齐缺失实体：新增 ${createdCount}，跳过已存在 ${skippedCount}。`,
                        `Scene ${sceneLabel} subject supplement completed: created ${createdCount}, skipped existing ${skippedCount}.`
                    ),
                    'success'
                );
            }
            if (!silent) {
                const lines = [
                    t(`场景 ${sceneLabel} 实体补齐完成`, `Scene ${sceneLabel} subject supplement completed`),
                    t(`新增：${createdCount}`, `Created: ${createdCount}`),
                    t(`已存在跳过：${skippedCount}`, `Skipped existing: ${skippedCount}`),
                    t(`失败：${failedCount}`, `Failed: ${failedCount}`),
                ];
                alert(lines.join('\n'));
            }
            return report;
        } finally {
            setSceneSubjectSupplementingMap((prev) => ({ ...prev, [statusKey]: false }));
        }
    }

    const buildSceneContentMarkdown = (sceneRows = []) => {
        if (!activeEpisode) return '';
        const contextInfo = `Project: ${project?.title || 'Unknown'} | Episode: ${activeEpisode?.title || 'Unknown'}\n`;
        const header = `| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Original Script Text | Environment Name | Environment Relation | Entry State | Exit State | Linked Characters | Key Props |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|`;
        const clean = (txt) => {
            let normalized = '';
            if (txt === null || txt === undefined) {
                normalized = '';
            } else if (typeof txt === 'string') {
                normalized = txt;
            } else if (typeof txt === 'number' || typeof txt === 'boolean') {
                normalized = String(txt);
            } else {
                try {
                    normalized = JSON.stringify(txt);
                } catch {
                    normalized = String(txt);
                }
            }
            return normalized.replace(/\n/g, '<br>').replace(/\|/g, '\\|');
        };
        const content = (sceneRows || []).map((s) => (
            `| ${clean(activeEpisode?.id)} | ${clean(s.id)} | ${clean(s.scene_no)} | ${clean(s.scene_name)} | ${clean(s.equivalent_duration)} | ${clean(s.core_scene_info)} | ${clean(s.original_script_text)} | ${clean(s.environment_name)} | ${clean(s.environment_relation || '')} | ${clean(s.entry_state || '')} | ${clean(s.exit_state || '')} | ${clean(s.linked_characters)} | ${clean(s.key_props)} |`
        )).join('\n');
        return `${contextInfo}${header}\n${content}`;
    };

    const normalizeSubjectType = (rawType, fallback = 'character') => {
        const normalized = String(rawType || '').trim().toLowerCase().replace(/[\s_\-]/g, '');
        if (['character', 'characters', 'char', 'role', 'roles', 'people', 'person', '人物', '角色'].includes(normalized)) {
            return 'character';
        }
        if (['prop', 'props', 'item', 'items', 'object', '道具', '物件'].includes(normalized)) {
            return 'prop';
        }
        if (['environment', 'environments', 'env', 'scene', 'scenes', '场景', '环境'].includes(normalized)) {
            return 'environment';
        }
        return fallback;
    };

    const buildSceneRegenImportSummaryLines = useCallback((report) => {
        const summary = report && typeof report === 'object' ? report : {};
        const jsonCountByType = (summary.subjects_json_count_by_type && typeof summary.subjects_json_count_by_type === 'object')
            ? summary.subjects_json_count_by_type
            : {
                character: 0,
                prop: 0,
                environment: 0,
            };
        const byType = (summary.by_type && typeof summary.by_type === 'object')
            ? summary.by_type
            : {
                character: { created: 0, skipped: 0 },
                prop: { created: 0, skipped: 0 },
                environment: { created: 0, skipped: 0 },
            };

        const llmTotal = Number(summary.subjects_json_count || 0)
            || (Number(jsonCountByType.character || 0) + Number(jsonCountByType.prop || 0) + Number(jsonCountByType.environment || 0));
        const createdTotal = Number(summary.created_count || 0);
        const skippedTotal = Number(summary.skipped_count || 0);

        return [
            t(
                `LLM 补充实体总数：${llmTotal}（角色 ${Number(jsonCountByType.character || 0)} / 场景 ${Number(jsonCountByType.environment || 0)} / 道具 ${Number(jsonCountByType.prop || 0)}）`,
                `LLM suggested entities: ${llmTotal} (characters ${Number(jsonCountByType.character || 0)} / environments ${Number(jsonCountByType.environment || 0)} / props ${Number(jsonCountByType.prop || 0)})`
            ),
            t(
                `实际新增导入：${createdTotal}（角色 ${Number(byType.character?.created || 0)} / 场景 ${Number(byType.environment?.created || 0)} / 道具 ${Number(byType.prop?.created || 0)}）`,
                `Actually imported as new: ${createdTotal} (characters ${Number(byType.character?.created || 0)} / environments ${Number(byType.environment?.created || 0)} / props ${Number(byType.prop?.created || 0)})`
            ),
            t(
                `识别为已存在并跳过：${skippedTotal}（角色 ${Number(byType.character?.skipped || 0)} / 场景 ${Number(byType.environment?.skipped || 0)} / 道具 ${Number(byType.prop?.skipped || 0)}）`,
                `Recognized as existing and skipped: ${skippedTotal} (characters ${Number(byType.character?.skipped || 0)} / environments ${Number(byType.environment?.skipped || 0)} / props ${Number(byType.prop?.skipped || 0)})`
            ),
        ];
    }, [t]);

    const showSceneRegenImportSummaryAlert = useCallback((report, options = {}) => {
        const summary = report && typeof report === 'object' ? report : {};
        const isReimport = Boolean(options?.isReimport);
        const generatedSceneCount = Number(options?.generatedSceneCount || 0);
        const lines = Array.isArray(summary.summary_lines) ? summary.summary_lines : buildSceneRegenImportSummaryLines(summary);
        const header = isReimport
            ? t('补实体完成', 'Entity Patch Completed')
            : (summary.entity_only_mode
                ? t('补充实体完成', 'Entity Supplement Completed')
                : t('补充实体完成', 'Entity Supplement Completed'));

        const detailLines = [header];
        if (!isReimport && !summary.entity_only_mode) {
            detailLines.push(
                t(
                    `新场景数：${generatedSceneCount}`,
                    `Generated scenes: ${generatedSceneCount}`
                )
            );
        }
        detailLines.push(...lines);
        alert(detailLines.join('\n'));
    }, [buildSceneRegenImportSummaryLines, t]);

    const importSubjectsFromRegeneratedJson = useCallback(async (subjectsJson) => {
        const payload = (subjectsJson && typeof subjectsJson === 'object') ? subjectsJson : null;
        if (!projectId || !payload) {
            return {
                created: 0,
                skipped: 0,
                createdItems: [],
                skippedItems: [],
                byType: {
                    character: { created: 0, skipped: 0 },
                    environment: { created: 0, skipped: 0 },
                    prop: { created: 0, skipped: 0 },
                },
            };
        }

        const normalizeKey = (key) => String(key || '').toLowerCase().replace(/[\s_\-]/g, '');
        const readArray = (source, aliases) => {
            if (!source || typeof source !== 'object') return [];
            const aliasSet = new Set((aliases || []).map(normalizeKey));
            for (const [rawKey, rawValue] of Object.entries(source)) {
                if (Array.isArray(rawValue) && aliasSet.has(normalizeKey(rawKey))) {
                    return rawValue;
                }
            }
            return [];
        };

        const splitTypedItems = (items) => {
            const next = { characters: [], props: [], environments: [] };
            for (const item of (items || [])) {
                if (!item || typeof item !== 'object') continue;
                const itemType = normalizeKey(item.type || item.subject_type || item.entity_type || '');
                if (['character', 'characters', 'char', 'role', 'roles', '人物', '角色'].includes(itemType)) {
                    next.characters.push(item);
                } else if (['prop', 'props', 'item', 'items', '道具', '物件'].includes(itemType)) {
                    next.props.push(item);
                } else if (['environment', 'environments', 'env', 'scene', '场景', '环境'].includes(itemType)) {
                    next.environments.push(item);
                }
            }
            return next;
        };

        const normalizedPayload = (() => {
            const direct = {
                characters: readArray(payload, ['characters', 'character', 'chars', 'roles', 'people', '人物', '角色']),
                props: readArray(payload, ['props', 'prop', 'items', '道具', '物件']),
                environments: readArray(payload, ['environments', 'environment', 'env', 'scenes', '场景', '环境']),
            };
            if (direct.characters.length || direct.props.length || direct.environments.length) {
                return direct;
            }

            const wrapped = payload.entities || payload.entity || payload.subjects || payload.subject || null;
            if (wrapped && typeof wrapped === 'object' && !Array.isArray(wrapped)) {
                return {
                    characters: readArray(wrapped, ['characters', 'character', 'chars', 'roles', 'people', '人物', '角色']),
                    props: readArray(wrapped, ['props', 'prop', 'items', '道具', '物件']),
                    environments: readArray(wrapped, ['environments', 'environment', 'env', 'scenes', '场景', '环境']),
                };
            }

            const mixedItems = readArray(payload, ['entities', 'entity', 'subjectlist', 'subjects']);
            if (mixedItems.length) {
                return splitTypedItems(mixedItems);
            }

            return {
                characters: Array.isArray(payload?.characters) ? payload.characters : [],
                props: Array.isArray(payload?.props) ? payload.props : [],
                environments: Array.isArray(payload?.environments) ? payload.environments : [],
            };
        })();

        const plannedByType = {
            character: Array.isArray(normalizedPayload.characters) ? normalizedPayload.characters.length : 0,
            prop: Array.isArray(normalizedPayload.props) ? normalizedPayload.props.length : 0,
            environment: Array.isArray(normalizedPayload.environments) ? normalizedPayload.environments.length : 0,
        };

        let importReport = null;
        if (typeof onImportText !== 'function') {
            return {
                created: 0,
                skipped: plannedByType.character + plannedByType.prop + plannedByType.environment,
                createdItems: [],
                skippedItems: [],
                byType: {
                    character: { created: 0, skipped: plannedByType.character },
                    prop: { created: 0, skipped: plannedByType.prop },
                    environment: { created: 0, skipped: plannedByType.environment },
                },
            };
        }

        try {
            importReport = await onImportText(JSON.stringify(normalizedPayload, null, 2), 'json');
        } catch (error) {
            throw new Error(error?.message || String(error || 'Import failed'));
        }

        const importedCounts = {
            character: Number(importReport?.importedSubjectCounts?.character || 0),
            prop: Number(importReport?.importedSubjectCounts?.prop || 0),
            environment: Number(importReport?.importedSubjectCounts?.environment || 0),
        };
        const createdItems = Array.isArray(importReport?.createdSubjectItems) ? importReport.createdSubjectItems : [];
        const skippedItems = Array.isArray(importReport?.skippedSubjectItems) ? importReport.skippedSubjectItems : [];

        const byType = {
            character: {
                created: importedCounts.character,
                skipped: Math.max(0, plannedByType.character - importedCounts.character),
            },
            prop: {
                created: importedCounts.prop,
                skipped: Math.max(0, plannedByType.prop - importedCounts.prop),
            },
            environment: {
                created: importedCounts.environment,
                skipped: Math.max(0, plannedByType.environment - importedCounts.environment),
            },
        };

        const created = byType.character.created + byType.prop.created + byType.environment.created;
        const skipped = byType.character.skipped + byType.prop.skipped + byType.environment.skipped;

        try {
            const refreshed = await fetchEntities(projectId);
            setEntities(Array.isArray(refreshed) ? refreshed : []);
        } catch {
            // Non-blocking refresh failure.
        }

        return {
            created,
            skipped,
            createdItems,
            skippedItems,
            byType,
        };
    }, [projectId, onImportText]);

    const persistSceneRegenSubjectsReport = useCallback(async (report) => {
        if (!activeEpisode?.id || !report) return false;
        const currentEpisodeInfo = (activeEpisode?.episode_info && typeof activeEpisode.episode_info === 'object')
            ? activeEpisode.episode_info
            : {};
        const nextEpisodeInfo = {
            ...currentEpisodeInfo,
            scene_regen_subjects_result: report,
        };
        await updateEpisode(activeEpisode.id, { episode_info: nextEpisodeInfo });
        return true;
    }, [activeEpisode?.id, activeEpisode?.episode_info]);

    const flushSceneAutoSave = useCallback(async (sceneCandidate) => {
        if (!activeEpisode?.id || !sceneCandidate?.id) return;

        const payload = buildSceneSavePayload(sceneCandidate);
        const snapshot = JSON.stringify(payload);
        const lastSnapshot = sceneAutoSavedSnapshotRef.current;
        if (lastSnapshot.sceneId === sceneCandidate.id && lastSnapshot.snapshot === snapshot) return;

        if (sceneAutoSaveInFlightRef.current) {
            sceneAutoSaveQueuedRef.current = sceneCandidate;
            return;
        }

        sceneAutoSaveInFlightRef.current = true;
        try {
            await updateScene(sceneCandidate.id, payload);
            const nextScenes = (scenes || []).map((sceneRow) => (
                sceneRow.id === sceneCandidate.id ? { ...sceneRow, ...payload } : sceneRow
            ));
            setScenes(nextScenes);
            setEditingScene((prev) => (prev?.id === sceneCandidate.id ? { ...prev, ...payload } : prev));
            await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(nextScenes) });
            sceneAutoSavedSnapshotRef.current = { sceneId: sceneCandidate.id, snapshot };
        } catch (e) {
            onLog?.(`Scene auto-save failed - ${e?.message || 'Unknown error'}`, 'error');
        } finally {
            sceneAutoSaveInFlightRef.current = false;
            const queued = sceneAutoSaveQueuedRef.current;
            sceneAutoSaveQueuedRef.current = null;
            if (queued?.id) {
                void flushSceneAutoSave(queued);
            }
        }
    }, [activeEpisode?.id, buildSceneSavePayload, buildSceneContentMarkdown, onLog, scenes]);

    const scheduleSceneAutoSave = useCallback((sceneCandidate) => {
        if (!activeEpisode?.id || !sceneCandidate?.id) return;
        sceneAutoSaveDraftRef.current = sceneCandidate;
        if (sceneAutoSaveTimerRef.current) {
            clearTimeout(sceneAutoSaveTimerRef.current);
            sceneAutoSaveTimerRef.current = null;
        }
        sceneAutoSaveTimerRef.current = setTimeout(() => {
            const latest = sceneAutoSaveDraftRef.current;
            if (latest?.id) {
                void flushSceneAutoSave(latest);
            }
        }, 900);
    }, [activeEpisode?.id, flushSceneAutoSave]);

    const handleSceneUpdate = (updatedScene) => {
        setScenes(prev => prev.map(s => s.id === updatedScene.id ? updatedScene : s));
        if (editingScene && editingScene.id === updatedScene.id) {
            setEditingScene(updatedScene);
        }
        scheduleSceneAutoSave(updatedScene);
    };

    const closeEditingScene = useCallback(async () => {
        if (sceneAutoSaveTimerRef.current) {
            clearTimeout(sceneAutoSaveTimerRef.current);
            sceneAutoSaveTimerRef.current = null;
        }
        if (editingScene?.id) {
            await flushSceneAutoSave(editingScene);
        }
        setEditingScene(null);
    }, [editingScene, flushSceneAutoSave]);

    useEffect(() => {
        if (!editingScene?.id) {
            sceneAutoSavedSnapshotRef.current = { sceneId: null, snapshot: '' };
            sceneAutoSaveDraftRef.current = null;
            return;
        }
        sceneAutoSavedSnapshotRef.current = {
            sceneId: editingScene.id,
            snapshot: buildSceneSnapshot(editingScene),
        };
    }, [editingScene?.id, buildSceneSnapshot]);

    useEffect(() => {
        setSceneRegenRequirements('');
        setSceneRegenEntityOnlyMode(true);
    }, [editingScene?.id]);

    useEffect(() => {
        const persisted = activeEpisode?.episode_info?.scene_regen_subjects_result;
        if (persisted && typeof persisted === 'object') {
            setSceneRegenSubjectsReport(persisted);
        }
    }, [activeEpisode?.id, activeEpisode?.episode_info?.scene_regen_subjects_result]);

    const handleReimportSceneRegenLlmContent = async () => {
        if (sceneRegenerating || sceneRegenReimporting || sceneRegenScenePatching) return;
        const report = sceneRegenSubjectsReport && typeof sceneRegenSubjectsReport === 'object'
            ? sceneRegenSubjectsReport
            : null;
        const subjectsJson = (report?.subjects_json && typeof report.subjects_json === 'object')
            ? report.subjects_json
            : null;

        if (!subjectsJson) {
            setSceneRegenProgress({
                phase: 'failed',
                percent: 100,
                message: t('重导入失败。', 'Re-import failed.'),
                error: t('没有可重导入的数据：上次补充实体结果未包含 subjects_json。请先重新执行一次“补充实体”。', 'No re-importable payload found: last entity supplement result does not include subjects_json. Please run Supplement Entities once first.'),
            });
            onLog?.(
                t('当前没有可重导入的重生成 LLM 内容（subjects_json 为空）。', 'No re-importable regenerated LLM payload found (subjects_json is empty).'),
                'warning'
            );
            return;
        }

        setSceneRegenReimporting(true);
        setSceneRegenProgress({
            phase: 'reimport_subjects_json',
            percent: 72,
            message: t('正在重新导入重生成 LLM 内容...', 'Re-importing regenerated LLM content...'),
            error: '',
        });

        try {
            const importResult = await importSubjectsFromRegeneratedJson(subjectsJson);
            const nextReport = {
                ...report,
                created_count: Number(importResult.created || 0),
                skipped_count: Number(importResult.skipped || 0),
                by_type: importResult.byType || report?.by_type || {
                    character: { created: 0, skipped: 0 },
                    environment: { created: 0, skipped: 0 },
                    prop: { created: 0, skipped: 0 },
                },
                created_items: Array.isArray(importResult.createdItems) ? importResult.createdItems : [],
                skipped_items: Array.isArray(importResult.skippedItems) ? importResult.skippedItems : [],
                reimport_count: Number(report?.reimport_count || 0) + 1,
                last_reimport_at: new Date().toISOString(),
                persisted: report?.persisted === true,
            };
            nextReport.summary_lines = buildSceneRegenImportSummaryLines(nextReport);

            try {
                const persisted = await persistSceneRegenSubjectsReport(nextReport);
                nextReport.persisted = !!persisted;
            } catch {
                nextReport.persisted = false;
            }

            setSceneRegenSubjectsReport(nextReport);
            setSceneRegenProgress({
                phase: 'done',
                percent: 100,
                message: t('重导入完成。', 'Re-import completed.'),
                error: '',
            });

            onLog?.(
                t(
                    `已重新导入重生成 LLM 内容：新增 ${importResult.created} 条，复用并跳过 ${importResult.skipped} 条。${(nextReport.summary_lines || []).join('；')}`,
                    `Re-imported regenerated LLM content: created ${importResult.created}, reused/skipped ${importResult.skipped}. ${(nextReport.summary_lines || []).join('; ')}`
                ),
                'success'
            );
            showSceneRegenImportSummaryAlert(nextReport, { isReimport: true });
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || t('重导入失败', 'Re-import failed');
            setSceneRegenProgress({
                phase: 'failed',
                percent: 100,
                message: t('重导入失败。', 'Re-import failed.'),
                error: String(detail || ''),
            });
            onLog?.(`${t('重导入失败', 'Re-import failed')}: ${detail}`, 'error');
        } finally {
            setSceneRegenReimporting(false);
        }
    };

    const handlePatchScenesFromRegenRawMarkdown = async () => {
        if (sceneRegenerating || sceneRegenReimporting || sceneRegenScenePatching) return;
        if (!activeEpisode?.id) {
            setSceneRegenProgress({
                phase: 'failed',
                percent: 100,
                message: t('补场景失败。', 'Patch scenes failed.'),
                error: t('未选择有效分集。', 'No active episode selected.'),
            });
            return;
        }

        const report = sceneRegenSubjectsReport && typeof sceneRegenSubjectsReport === 'object'
            ? sceneRegenSubjectsReport
            : null;
        const rawMarkdown = String(report?.raw_markdown || '').trim();
        if (!rawMarkdown) {
            setSceneRegenProgress({
                phase: 'failed',
                percent: 100,
                message: t('补场景失败。', 'Patch scenes failed.'),
                error: t('没有可补场景的数据：上次重生成结果未包含 raw_markdown。', 'No scene patch payload found: last regenerate result has no raw_markdown.'),
            });
            return;
        }

        setSceneRegenScenePatching(true);
        setSceneRegenProgress({
            phase: 'rebuild_scenes_from_raw',
            percent: 35,
            message: t('按 raw_markdown 解析场景并补录...', 'Parsing raw_markdown and patching scenes...'),
            error: '',
        });

        try {
            const parsedRows = parseScenesFromText(rawMarkdown);
            if (!Array.isArray(parsedRows) || parsedRows.length === 0) {
                throw new Error(t('raw_markdown 未解析到可导入场景行。', 'No importable scene rows parsed from raw_markdown.'));
            }

            setSceneRegenProgress({
                phase: 'rebuild_scenes_from_raw',
                percent: 62,
                message: t('正在按场次号补录场景...', 'Patching scenes by scene_no...'),
                error: '',
            });

            const latest = await fetchScenes(activeEpisode.id);
            const currentRows = Array.isArray(latest) ? latest : [];
            const bySceneNo = new Map();
            for (const row of currentRows) {
                const key = String(row?.scene_no || '').trim();
                if (key) bySceneNo.set(key, row);
            }

            let createdCount = 0;
            let updatedCount = 0;
            let failedCount = 0;

            for (const row of parsedRows) {
                const payload = buildSceneSavePayload(row);
                const sceneNoKey = String(payload?.scene_no || '').trim();
                try {
                    const matched = sceneNoKey ? bySceneNo.get(sceneNoKey) : null;
                    if (matched?.id) {
                        // eslint-disable-next-line no-await-in-loop
                        await updateScene(matched.id, payload);
                        updatedCount += 1;
                    } else {
                        // eslint-disable-next-line no-await-in-loop
                        await createScene(activeEpisode.id, payload);
                        createdCount += 1;
                    }
                } catch {
                    failedCount += 1;
                }
            }

            const mergedRows = await fetchScenes(activeEpisode.id);
            const normalizedRows = (mergedRows || []).map((scene) => ({
                ...scene,
                original_script_text: normalizeOriginalScriptText(scene?.original_script_text),
            }));
            setScenes(normalizedRows);
            if (normalizedRows.length > 0) {
                setEditingScene((prev) => {
                    if (prev?.id) {
                        const still = normalizedRows.find((s) => Number(s?.id) === Number(prev.id));
                        if (still) return still;
                    }
                    return normalizedRows[0];
                });
            }
            await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(normalizedRows) });

            const nextReport = {
                ...(report || {}),
                scene_patch: {
                    created_count: createdCount,
                    updated_count: updatedCount,
                    failed_count: failedCount,
                    patch_count: Number(report?.scene_patch?.patch_count || 0) + 1,
                    last_patch_at: new Date().toISOString(),
                },
                persisted: report?.persisted === true,
            };

            try {
                const persisted = await persistSceneRegenSubjectsReport(nextReport);
                nextReport.persisted = !!persisted;
            } catch {
                nextReport.persisted = false;
            }
            setSceneRegenSubjectsReport(nextReport);

            setSceneRegenProgress({
                phase: 'done',
                percent: 100,
                message: t('补场景完成。', 'Patch scenes completed.'),
                error: '',
            });

            onLog?.(
                t(
                    `补场景完成：新增 ${createdCount} 条，更新 ${updatedCount} 条，失败 ${failedCount} 条。`,
                    `Patch scenes completed: created ${createdCount}, updated ${updatedCount}, failed ${failedCount}.`
                ),
                failedCount > 0 ? 'warning' : 'success'
            );
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || t('补场景失败', 'Patch scenes failed');
            setSceneRegenProgress({
                phase: 'failed',
                percent: 100,
                message: t('补场景失败。', 'Patch scenes failed.'),
                error: String(detail || ''),
            });
            onLog?.(`${t('补场景失败', 'Patch scenes failed')}: ${detail}`, 'error');
        } finally {
            setSceneRegenScenePatching(false);
        }
    };

    const handleSave = async () => {
        if (!activeEpisode) return;
        
        onLog?.('SceneManager: Saving content...', 'info');
        
        try {
            const savedScenes = [];
            const failedScenes = [];

            for (const sceneRow of (scenes || [])) {
                const payload = buildSceneSavePayload(sceneRow);
                try {
                    if (sceneRow.id) {
                        await updateScene(sceneRow.id, payload);
                        savedScenes.push({ ...sceneRow, ...payload });
                    } else {
                        const created = await createScene(activeEpisode.id, payload);
                        savedScenes.push({ ...sceneRow, ...payload, id: created.id });
                    }
                } catch (e) {
                    failedScenes.push({ scene: sceneRow, error: e });
                    onLog?.(`Scene save failed: ${sceneRow?.scene_no || sceneRow?.id || 'unknown'} - ${e?.response?.data?.detail || e?.message || 'Unknown error'}`, 'error');
                }
            }

            if (savedScenes.length === 0 && failedScenes.length > 0) {
                throw new Error(failedScenes[0]?.error?.response?.data?.detail || failedScenes[0]?.error?.message || 'All scenes failed to save');
            }

            setScenes(savedScenes);

            await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(savedScenes) });
            if (failedScenes.length > 0) {
                onLog?.(`SceneManager: Partially saved (${savedScenes.length} ok, ${failedScenes.length} failed).`, 'warning');
            } else {
                onLog?.('SceneManager: Saved successfully.', 'success');
            }
        } catch(e) {
            console.error(e);
            onLog?.(`SceneManager: Save failed - ${e.message}`, 'error');
            alert(`Failed to save scenes: ${e?.message || 'Unknown error'}`);
        }
    };

    const getSceneImage = (scene) => {
        // Use environment_name as requested, cleaning markdown ** and []
        const sourceText = scene.environment_name || scene.location || '';
        const rawLoc = sourceText.replace(/[\[\]\*]/g, '').trim().toLowerCase();
        
        if (!rawLoc) return null;
        
        const cleanForMatch = (str) => (str || '').replace(/[（\(\)）]/g, '').trim().toLowerCase();
        const targetName = cleanForMatch(rawLoc);

        // Try exact match first
        let match = entities.find(e => {
            const cn = cleanForMatch(e.name);
            let en = (e.name_en || '').toLowerCase();
            
            // Fallback EN extract
            if (!en && e.description) {
                const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
            }
            const enClean = cleanForMatch(en);

            const isMatch = cn === targetName || enClean === targetName;
            
            return isMatch;
        });

        // Try fuzzy match if exact fails
        if (!match) {
             match = entities.find(e => {
                const cn = cleanForMatch(e.name);
                let en = (e.name_en || '').toLowerCase();
                // Fallback EN extract
                if (!en && e.description) {
                    const enMatch = e.description.match(/Name \(EN\):\s*([^\n\r]+)/i);
                    if (enMatch && enMatch[1]) en = enMatch[1].trim().split(/(?:\s+role:|\n|,)/)[0].trim().toLowerCase(); 
                }
                const enClean = cleanForMatch(en);

                if (cn && (cn.includes(targetName) || targetName.includes(cn))) {
                    return true;
                }
                if (enClean && (enClean.includes(targetName) || targetName.includes(enClean))) {
                    return true;
                }
                return false;
             });
        }

        return match ? match.image_url : null;
    };

    const finalizeAiShotsGenerationResult = useCallback(async ({ sceneId, result }) => {
        const generatedRows = Array.isArray(result?.content) ? result.content : [];
        const generatedRaw = String(result?.raw_text || '').trim();
        const generatedWarnings = Array.isArray(result?.warnings) ? result.warnings.map(w => String(w || '').trim()).filter(Boolean) : [];
        if (generatedRows.length === 0) {
            if (generatedRaw) {
                const rawPreview = generatedRaw.replace(/\s+/g, ' ').slice(0, 300);
                onLog?.(`SceneManager: Generate Shots returned 0 parsed rows. Raw preview: ${rawPreview}`, 'warning');
                console.warn('[SceneManager] Generate Shots parse-empty with raw_text preview', {
                    sceneId,
                    rawLen: generatedRaw.length,
                    rawPreview,
                });
                throw new Error(`Generate Shots returned 0 parsed rows; raw preview: ${rawPreview}`);
            }
            throw new Error('Generate Shots returned empty result (no rows and no raw text)');
        }

        onLog?.(`SceneManager: Shot list generated for Scene ${sceneId}.`, 'success');
        generatedWarnings.forEach((msg) => onLog?.(`SceneManager: ${msg}`, 'warning'));
        setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });

        const sceneObj = scenes.find(s => Number(s?.id) === Number(sceneId)) || { id: sceneId, scene_no: sceneId };
        setEditingScene(sceneObj);
        setAiShotsStaging(prev => ({
            ...prev,
            sceneId,
            content: generatedRows,
            rawText: result?.raw_text || '',
            usage: result?.usage || null,
            timestamp: result?.timestamp || null,
            warnings: generatedWarnings,
            loading: false,
            error: null,
        }));

        setAiShotsFlowStatus({
            phase: 'importing',
            sceneId,
            message: t('生成完成，正在自动导入 Shots...', 'Generated. Auto-importing into Shots...'),
        });
        onLog?.(`SceneManager: Auto-importing shots for Scene ${sceneId}...`, 'info');

        await applySceneAIResult(sceneId, { content: generatedRows });

        onLog?.(`SceneManager: Auto-import finished for Scene ${sceneId}.`, 'success');
        if (typeof onSwitchToShots === 'function' && consumeAiShotsAutoSwitchTicket(activeEpisode?.id)) {
            onSwitchToShots(sceneId);
        }
        setAiShotsFlowStatus({
            phase: 'completed',
            sceneId,
            message: t('AI Shots 已导入，已切换到 Shots 页面。', 'AI Shots imported. Switched to Shots page.'),
        });
    }, [activeEpisode?.id, consumeAiShotsAutoSwitchTicket, onLog, onSwitchToShots, scenes, t]);

    const isAiShotsFlowActive = ['preparing', 'generating', 'importing'].includes(String(aiShotsFlowStatus?.phase || '').toLowerCase());
    const isSceneAiShotsGenerating = useCallback((sceneId) => {
        const stableSceneId = Number(sceneId || 0);
        if (!Number.isFinite(stableSceneId) || stableSceneId <= 0) return false;
        const activeFlowSceneId = Number(aiShotsFlowStatus?.sceneId || 0);
        return aiShotsBusySceneIdsRef.current.has(stableSceneId)
            || (isAiShotsFlowActive && activeFlowSceneId === stableSceneId);
    }, [aiShotsFlowStatus?.sceneId, isAiShotsFlowActive]);
    const isSceneAiShotsBusy = useCallback((sceneId) => {
        const stableSceneId = Number(sceneId || 0);
        if (!Number.isFinite(stableSceneId) || stableSceneId <= 0) return false;
        return isSceneAiShotsGenerating(stableSceneId)
            || aiShotsPromptPreviewSceneIdsRef.current.has(stableSceneId);
    }, [isSceneAiShotsGenerating]);
    const closeSceneShotPromptModal = useCallback((sceneIdOverride = null) => {
        const stableSceneId = Number(sceneIdOverride || shotPromptModal?.sceneId || 0);
        if (Number.isFinite(stableSceneId) && stableSceneId > 0) {
            aiShotsPromptPreviewSceneIdsRef.current.delete(stableSceneId);
        }
        setShotPromptModal({ open: false, sceneId: null, data: null, loading: false });
    }, [shotPromptModal?.sceneId]);

    const resumeAiShotsFromTaskMarker = useCallback(async (marker) => {
        if (!activeEpisode?.id || !marker?.taskId || !marker?.sceneId) return;
        if (aiShotsResumeInFlightRef.current) return;
        aiShotsResumeInFlightRef.current = true;

        const sceneId = Number(marker.sceneId);
        const startedAt = Number(marker?.startedAt || Date.now());
        const elapsedMs = Math.max(0, Date.now() - startedAt);
        const remainingTimeoutMs = Math.max(0, ANALYSIS_TASK_MAX_AGE_MS - elapsedMs);
        if (remainingTimeoutMs <= 0) {
            clearAiShotsTaskMarker(activeEpisode.id, sceneId);
            setAiShotsFlowStatus({
                phase: 'failed',
                sceneId,
                message: t('检测到过期的 AI Shots 任务恢复标记，已自动清理。', 'Detected an expired AI Shots task marker and cleared it automatically.'),
            });
            aiShotsResumeInFlightRef.current = false;
            return;
        }
        setAiShotsFlowStatus({
            phase: 'generating',
            sceneId,
            message: t('检测到进行中的 AI Shots 任务，正在恢复状态...', 'Detected an in-progress AI Shots task, reconnecting...'),
        });

        try {
            const result = await waitForAsyncTask(marker.taskId, { interval: 2500, timeout: remainingTimeoutMs });
            clearAiShotsTaskMarker(activeEpisode.id, sceneId);
            await finalizeAiShotsGenerationResult({ sceneId, result });
        } catch (e) {
            const canceled = Boolean(e?.isCanceled) || Number(e?.errorCode || e?.response?.status || 0) === 499;
            clearAiShotsTaskMarker(activeEpisode.id, sceneId);
            setAiShotsFlowStatus(
                canceled
                    ? {
                        phase: 'failed',
                        sceneId,
                        message: t('AI Shots 任务已停止。', 'AI Shots task was stopped.'),
                    }
                    : {
                        phase: 'failed',
                        sceneId,
                        message: t(`AI Shots 失败：${e?.message || e}`, `AI Shots failed: ${e?.message || e}`),
                    }
            );
            onLog?.(`SceneManager: Failed to resume AI Shots task - ${e?.message || e}`, canceled ? 'warning' : 'error');
        } finally {
            aiShotsResumeInFlightRef.current = false;
        }
    }, [activeEpisode?.id, clearAiShotsTaskMarker, finalizeAiShotsGenerationResult, onLog, t]);

    useEffect(() => {
        if (!activeEpisode?.id) return;
        const marker = loadAiShotsTaskMarker(activeEpisode.id);
        if (!marker?.taskId || !marker?.sceneId) return;
        if (aiShotsFlowStatus.phase === 'generating' || aiShotsFlowStatus.phase === 'importing') return;
        resumeAiShotsFromTaskMarker(marker);
    }, [activeEpisode?.id, aiShotsFlowStatus.phase, loadAiShotsTaskMarker, resumeAiShotsFromTaskMarker]);

    const executeGenerateShots = async ({ sceneId, promptData }) => {
        const stableSceneId = Number(sceneId || 0);
        if (!Number.isFinite(stableSceneId) || stableSceneId <= 0) return;
        if (isSceneAiShotsGenerating(stableSceneId)) return;

        aiShotsPromptPreviewSceneIdsRef.current.delete(stableSceneId);
        aiShotsBusySceneIdsRef.current.add(stableSceneId);
        armAiShotsAutoSwitchTicket(activeEpisode?.id, sceneId);
        setAiShotsFlowStatus({
            phase: 'generating',
            sceneId,
            message: t('AI Shots 生成中...', 'AI Shots generating...'),
        });
        onLog?.(`SceneManager: Generating shots for Scene ${sceneId}...`, 'info');

        try {
            const startedAt = Date.now();
            const result = await generateSceneShots(sceneId, {
                user_prompt: promptData?.user_prompt,
                system_prompt: promptData?.system_prompt,
            }, {
                onTaskCreated: (taskId) => {
                    saveAiShotsTaskMarker(activeEpisode?.id, {
                        taskId,
                        sceneId,
                        startedAt,
                    });
                },
            });
            clearAiShotsTaskMarker(activeEpisode?.id, sceneId);
            await finalizeAiShotsGenerationResult({ sceneId, result });
        } catch (e) {
            console.error(e);
            clearAiShotsTaskMarker(activeEpisode?.id, sceneId);
            onLog?.(`SceneManager: Failed to generate/apply shots - ${e.message}`, 'error');
            setAiShotsFlowStatus({
                phase: 'failed',
                sceneId,
                message: t(`AI Shots 失败：${e.message}`, `AI Shots failed: ${e.message}`),
            });
            alert("Failed to generate shots: " + e.message);
            setShotPromptModal(prev => ({ ...prev, loading: false }));
        } finally {
            aiShotsBusySceneIdsRef.current.delete(stableSceneId);
        }
    };

    const handleGenerateShots = async (sceneId) => {
        if (!sceneId) {
            alert("Please save the scene list first to create database records before generating shots.");
            return;
        }

        if (isSceneAiShotsBusy(sceneId)) {
            onLog?.(t('当前场景的 AI 镜头任务已在运行，请等待完成。', 'AI shots for this scene are already running. Please wait.'), 'warning');
            return;
        }

        if (isSuperuser) {
            aiShotsPromptPreviewSceneIdsRef.current.add(Number(sceneId));
            setShotPromptModal({ open: true, sceneId: sceneId, data: null, loading: true });
            try {
                const data = await fetchSceneShotsPrompt(sceneId);
                setShotPromptModal({ open: true, sceneId: sceneId, data: data, loading: false });
            } catch (e) {
                onLog?.(`SceneManager: Failed to fetch prompt preview - ${e.message}`, 'error');
                setAiShotsFlowStatus({
                    phase: 'failed',
                    sceneId,
                    message: t(`AI Shots 预览加载失败：${e.message}`, `Failed to load AI Shots preview: ${e.message}`),
                });
                closeSceneShotPromptModal(sceneId);
                alert(t(`AI Shots 预览加载失败：${e.message}`, `Failed to load AI Shots preview: ${e.message}`));
            }
            return;
        }

        try {
            setAiShotsFlowStatus({
                phase: 'preparing',
                sceneId,
                message: t('正在准备 AI Shots 请求...', 'Preparing AI Shots request...'),
            });
            onLog?.('SceneManager: Non-superuser mode: skip prompt preview and run main AI Shots flow directly.', 'info');
            await executeGenerateShots({ sceneId, promptData: null });
        } catch (e) {
            onLog?.(`SceneManager: Failed to start AI shots main flow - ${e.message}`, 'error');
            setAiShotsFlowStatus({
                phase: 'failed',
                sceneId,
                message: t(`AI Shots 失败：${e.message}`, `AI Shots failed: ${e.message}`),
            });
            alert(`Failed to generate AI shots: ${e.message}`);
        }
    };

    const handleDeleteScene = async (scene) => {
        if (!scene?.id) {
            const remaining = scenes.filter(s => s !== scene);
            setScenes(remaining);
            if (activeEpisode?.id) {
                try {
                    await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(remaining) });
                } catch (e) {
                    console.warn('Failed to sync scene_content after local scene removal', e);
                }
            }
            return;
        }
        const label = scene.scene_no || scene.scene_name || `#${scene.id}`;
        if (!await confirmUiMessage(`Delete scene ${label}?`)) return;

        try {
            await deleteScene(scene.id);
            const remaining = scenes.filter(s => s.id !== scene.id);
            setScenes(remaining);
            if (editingScene?.id === scene.id) {
                setEditingScene(null);
            }
            if (activeEpisode?.id) {
                await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(remaining) });
            }
            onLog?.(`Scene deleted: ${label}`, 'success');
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'Failed to delete scene';
            onLog?.(`Scene delete failed: ${detail}`, 'error');
            alert(`Failed to delete scene: ${detail}`);
        }
    };

    const buildSceneRegenUserPromptPreview = (sceneRow, requirements) => {
        const scene = sceneRow || {};
        const reqText = String(requirements || '').trim() || defaultSceneRegenRequirement;
        const projectInfo = (project?.global_info && typeof project.global_info === 'object')
            ? project.global_info
            : {};

        const projectContextLines = [
            `Project Title: ${project?.title || ''}`,
            `Episode Title: ${activeEpisode?.title || ''}`,
            projectInfo?.script_title ? `Script Title: ${projectInfo.script_title}` : '',
            projectInfo?.series_episode ? `Series Episode: ${projectInfo.series_episode}` : '',
            projectInfo?.type ? `Type: ${projectInfo.type}` : '',
            projectInfo?.base_positioning ? `Base Positioning: ${projectInfo.base_positioning}` : '',
            projectInfo?.language ? `Language: ${projectInfo.language}` : '',
            projectInfo?.Global_Style ? `Global Style: ${projectInfo.Global_Style}` : '',
            projectInfo?.tone ? `Tone: ${projectInfo.tone}` : '',
            projectInfo?.lighting ? `Lighting: ${projectInfo.lighting}` : '',
            Array.isArray(projectInfo?.borrowed_films) && projectInfo.borrowed_films.length > 0
                ? `Borrowed Films: ${projectInfo.borrowed_films.join(', ')}`
                : '',
        ].filter(Boolean);

        const bucket = {
            character: [],
            environment: [],
            prop: [],
        };
        const seen = new Set();
        (Array.isArray(entities) ? entities : []).forEach((entity) => {
            const type = normalizeSubjectType(entity?.type || entity?.subject_type || entity?.entity_type, 'character');
            if (!bucket[type]) return;
            const names = [entity?.name, entity?.name_en]
                .map((v) => String(v || '').trim())
                .filter(Boolean);
            names.forEach((name) => {
                const key = `${type}:${normalizeSubjectKey(name)}`;
                if (seen.has(key)) return;
                seen.add(key);
                bucket[type].push(name);
            });
        });

        const formatLine = (typeKey, label) => {
            const list = bucket[typeKey] || [];
            if (list.length === 0) return `${label}: (none)`;
            const shown = list.slice(0, 80);
            const suffix = list.length > shown.length ? ` ... (+${list.length - shown.length} more)` : '';
            return `${label} (${list.length}): ${shown.join(', ')}${suffix}`;
        };

        const existingEntityBlock = [
            'Existing Entity Inventory By Category (project baseline dependencies; reusable as-is; DO NOT rewrite/rename/redefine):',
            formatLine('character', 'characters'),
            formatLine('prop', 'props'),
            formatLine('environment', 'environments'),
            'Constraint: Existing entities are immutable references for this regeneration. You may depend on them, but must not overwrite or regenerate them.',
        ].join('\n');

        return [
            '[Project Context]',
            ...projectContextLines,
            `Source Scene Database ID: ${scene?.id || ''}`,
            '',
            '[Current Scene]',
            `Scene No: ${scene?.scene_no || ''}`,
            `Scene Name: ${scene?.scene_name || ''}`,
            `Equivalent Duration: ${scene?.equivalent_duration || ''}`,
            `Core Scene Info: ${scene?.core_scene_info || ''}`,
            `Original Script Text: ${scene?.original_script_text || ''}`,
            `Environment Name: ${scene?.environment_name || ''}`,
            `Linked Characters: ${scene?.linked_characters || ''}`,
            `Key Props: ${scene?.key_props || ''}`,
            '',
            '[Original Script Grounding]',
            `${scene?.original_script_text || ''}`,
            '',
            '[System-level Subjects Inventory]',
            existingEntityBlock,
            '',
            '[User Supplement Requirements]',
            reqText,
            '',
            '[Grounding Reminder]',
            'Use Original Script Grounding to verify whether the current scene is missing characters or has major core scene info / visual-guidance omissions or obvious errors. Minor wording differences that do not affect plot or staging may be ignored. If material omissions or obvious errors exist, repair the scene markdown row patch and keep SUBJECTS_JSON consistent with the repaired row.',
        ].join('\n');
    };

    const openSceneRegenPromptModal = async (sceneRow, requirements) => {
        setSceneRegenPromptModal({ open: true, loading: true, data: null });
        try {
            const res = await fetchPrompt('scene_regenerate.txt');
            const sysPrompt = String(res?.content || '').trim();
            const userPreview = buildSceneRegenUserPromptPreview(sceneRow, requirements);
            setSceneRegenPromptModal({
                open: true,
                loading: false,
                data: {
                    system_prompt: sysPrompt,
                    user_prompt_preview: userPreview,
                },
            });
        } catch (e) {
            setSceneRegenPromptModal({ open: false, loading: false, data: null });
            const status = Number(e?.status || 0);
            const detail = String(e?.message || e || '').trim() || 'Unknown error';
            console.error('[SceneManager] Failed to load regeneration prompt', {
                filename: 'scene_regenerate.txt',
                status: status || null,
                detail,
                debug: e?.debug || null,
                error: e,
            });
            onLog?.(
                `SceneManager: Failed to load regeneration prompt 'scene_regenerate.txt'${status ? ` (HTTP ${status})` : ''} - ${detail}`,
                'error'
            );
            const alertDetail = detail.length > 600 ? `${detail.slice(0, 600)}...` : detail;
            alert(
                t(
                    `加载补充实体提示词失败：${alertDetail}`,
                    `Failed to load entity supplement prompt: ${alertDetail}`,
                )
            );
        }
    };

    const handleRegenerateScene = async (superuserPromptData = null) => {
        if (!editingScene?.id) {
            alert(t('请先保存当前场景。', 'Please save current scene first.'));
            return;
        }

        const requirements = String(sceneRegenRequirements || '').trim() || defaultSceneRegenRequirement;

        if (isSuperuser && !superuserPromptData) {
            await openSceneRegenPromptModal(editingScene, requirements);
            return;
        }

        const label = editingScene.scene_no || editingScene.scene_name || `#${editingScene.id}`;
        const confirmed = await confirmUiMessage(
            t(
                (sceneRegenEntityOnlyMode
                    ? `将按“仅补实体”模式执行补充实体：注入项目信息、现有 subjects、当前场景内容、原始剧本文本与补充要求；除补缺失实体外，还会按原始剧本文本校对角色缺失与核心场景信息/视觉指导缺失，并在需要时回写当前场景行。目标：${label}。是否继续？`
                    : `将为场景 ${label} 执行补充实体，并按原始剧本文本校对场景内容，在需要时补充新场景行与实体。是否继续？`),
                (sceneRegenEntityOnlyMode
                    ? `Run scene entity supplement mode for ${label}: inject project context, existing subjects, current scene content, original script text, and user requirements; supplement missing entities and repair the current scene row when original-script grounding shows missing characters or major core-scene omissions/errors. Continue?`
                    : `Run Supplement Entities for ${label}: supplement missing entities and use original script grounding to repair scene rows when needed. Continue?`)
            )
        );
        if (!confirmed) return;

        setSceneRegenerating(true);
        setSceneRegenSubjectsReport(null);
        setSceneRegenProgress({
            phase: 'preflight',
            percent: 8,
            message: t('预检场景状态...', 'Preflight checking scene state...'),
            error: '',
        });
        try {
            // Preflight: scene ID may become stale after list refresh/replacement; resolve latest DB row first.
            let targetScene = editingScene;
            if (activeEpisode?.id) {
                try {
                    const latestScenes = await fetchScenes(activeEpisode.id);
                    const byId = (latestScenes || []).find((s) => Number(s?.id) === Number(editingScene?.id));
                    if (byId) {
                        targetScene = { ...byId, ...editingScene, id: byId.id };
                    } else {
                        const editingSceneNo = String(editingScene?.scene_no || '').trim();
                        const bySceneNo = editingSceneNo
                            ? (latestScenes || []).find((s) => String(s?.scene_no || '').trim() === editingSceneNo)
                            : null;
                        if (bySceneNo) {
                            targetScene = { ...bySceneNo, ...editingScene, id: bySceneNo.id };
                            setEditingScene(targetScene);
                        } else {
                            setScenes((latestScenes || []).map((scene) => ({
                                ...scene,
                                original_script_text: normalizeOriginalScriptText(scene?.original_script_text),
                            })));
                            setEditingScene(null);
                            throw new Error(t('目标场景已不存在，请刷新后重新选择场景再重生成。', 'Target scene no longer exists. Refresh and reselect the scene before regenerating.'));
                        }
                    }
                } catch (preflightErr) {
                    if (String(preflightErr?.message || '').trim()) {
                        throw preflightErr;
                    }
                }
            }

            setSceneRegenProgress({
                phase: 'autosave',
                percent: 18,
                message: t('同步当前编辑内容...', 'Syncing current scene edits...'),
                error: '',
            });
            await flushSceneAutoSave(targetScene);

            const oldSceneId = targetScene.id;
            setSceneRegenProgress({
                phase: 'llm',
                percent: 38,
                message: t('提交补充实体提示词到 LLM...', 'Submitting entity supplement prompt to LLM...'),
                error: '',
            });
            const result = await regenerateScene(oldSceneId, {
                user_requirements: requirements,
                system_prompt: String(superuserPromptData?.system_prompt || '').trim() || undefined,
                entity_only_mode: !!sceneRegenEntityOnlyMode,
            });

            const generated = Array.isArray(result?.scenes) ? result.scenes : [];
            if (generated.length === 0) {
                throw new Error(t('未返回可用的新场景。', 'No regenerated scenes returned.'));
            }

            const isEntityOnlyMode = Boolean(result?.entity_only_mode || sceneRegenEntityOnlyMode);

            setSceneRegenProgress({
                phase: 'replace_scene',
                percent: 58,
                message: isEntityOnlyMode
                    ? t('仅补实体模式：按 markdown 行补丁回写当前场景...', 'Entity-only mode: applying markdown row patch to current scene...')
                    : t('替换旧场景并刷新列表...', 'Replacing old scene and refreshing list...'),
                error: '',
            });

            let mergedRows = Array.isArray(generated) ? generated : [];
            if (activeEpisode?.id) {
                try {
                    const latestScenes = await fetchScenes(activeEpisode.id);
                    mergedRows = (latestScenes || []).map((scene) => ({
                        ...scene,
                        original_script_text: normalizeOriginalScriptText(scene?.original_script_text),
                    }));
                } catch {
                    if (!isEntityOnlyMode) {
                        const currentRows = Array.isArray(scenes) ? scenes : [];
                        const oldIndex = currentRows.findIndex((s) => s.id === oldSceneId);
                        const nextRows = [...currentRows];
                        if (oldIndex >= 0) {
                            nextRows.splice(oldIndex, 1, ...generated);
                        } else {
                            nextRows.push(...generated);
                        }
                        mergedRows = nextRows;
                    } else {
                        mergedRows = Array.isArray(scenes) ? scenes : [];
                    }
                }
            }

            setScenes(mergedRows);
            if (isEntityOnlyMode) {
                const focusScene = mergedRows.find((item) => Number(item?.id || 0) === Number(oldSceneId || 0)) || mergedRows[0] || null;
                setEditingScene(focusScene);
            } else {
                const generatedIdSet = new Set(generated.map((item) => Number(item?.id || 0)).filter((v) => v > 0));
                const focusScene = mergedRows.find((item) => generatedIdSet.has(Number(item?.id || 0))) || mergedRows[0] || null;
                setEditingScene(focusScene);
            }

            if (activeEpisode?.id) {
                await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(mergedRows) });
            }

            setSceneRegenProgress({
                phase: 'import_subjects_json',
                percent: 78,
                message: t('按 subjects JSON 增量导入实体...', 'Incrementally importing entities from subjects JSON...'),
                error: '',
            });
            const subjectsJson = (result?.subjects_json && typeof result.subjects_json === 'object')
                ? result.subjects_json
                : null;
            let importResult = {
                created: 0,
                skipped: 0,
                createdItems: [],
                skippedItems: [],
                byType: {
                    character: { created: 0, skipped: 0 },
                    environment: { created: 0, skipped: 0 },
                    prop: { created: 0, skipped: 0 },
                },
            };
            if (subjectsJson) {
                importResult = await importSubjectsFromRegeneratedJson(subjectsJson);
            } else {
                onLog?.(
                    t('重生成返回未包含 subjects_json，本次未执行实体补全导入。', 'Regeneration response did not include subjects_json; skipped subject import for this run.'),
                    'warning'
                );
            }

            const rawSubjectsJsonCount = (result?.subjects_json_count && typeof result.subjects_json_count === 'object')
                ? result.subjects_json_count
                : {};
            const totalSubjectsJsonCount =
                Number(rawSubjectsJsonCount.characters || 0)
                + Number(rawSubjectsJsonCount.props || 0)
                + Number(rawSubjectsJsonCount.environments || 0);

            const sceneRegenSubjectResult = {
                source: 'scene_regenerate_subjects_json',
                source_scene_id: Number(oldSceneId || 0),
                source_scene_label: String(label || ''),
                generated_scene_count: Number(generated.length || 0),
                entity_only_mode: Boolean(result?.entity_only_mode || sceneRegenEntityOnlyMode),
                subjects_json_count: totalSubjectsJsonCount,
                subjects_json_count_by_type: {
                    character: Number(rawSubjectsJsonCount.characters || 0),
                    prop: Number(rawSubjectsJsonCount.props || 0),
                    environment: Number(rawSubjectsJsonCount.environments || 0),
                },
                raw_markdown: String(result?.raw_markdown || ''),
                subjects_json: subjectsJson || { characters: [], props: [], environments: [] },
                created_count: Number(importResult.created || 0),
                skipped_count: Number(importResult.skipped || 0),
                by_type: importResult.byType || {
                    character: { created: 0, skipped: 0 },
                    environment: { created: 0, skipped: 0 },
                    prop: { created: 0, skipped: 0 },
                },
                created_items: Array.isArray(importResult.createdItems) ? importResult.createdItems : [],
                skipped_items: Array.isArray(importResult.skippedItems) ? importResult.skippedItems : [],
                reimport_count: 0,
                saved_at: new Date().toISOString(),
                persisted: false,
            };
            sceneRegenSubjectResult.summary_lines = buildSceneRegenImportSummaryLines(sceneRegenSubjectResult);

            try {
                const persisted = await persistSceneRegenSubjectsReport(sceneRegenSubjectResult);
                sceneRegenSubjectResult.persisted = !!persisted;
            } catch (persistErr) {
                onLog?.(
                    t(
                        `重生成实体结果持久化失败：${persistErr?.message || persistErr}`,
                        `Failed to persist regenerated entity result: ${persistErr?.message || persistErr}`
                    ),
                    'warning'
                );
            }

            setSceneRegenSubjectsReport(sceneRegenSubjectResult);

            setSceneRegenProgress({
                phase: 'done',
                percent: 100,
                message: t('重生成完成。', 'Regeneration completed.'),
                error: '',
            });

            onLog?.(
                t(
                    ((Boolean(result?.entity_only_mode || sceneRegenEntityOnlyMode))
                        ? `补充实体完成（仅补实体模式）：未替换场景/分镜，已按 markdown 行补丁回写当前场景，并校对环境锚点、关联角色、关键道具及核心场景信息；按 subjects_json 新增 ${importResult.created} 条（复用并跳过 ${importResult.skipped} 条）。${(sceneRegenSubjectResult.summary_lines || []).join('；')}`
                        : `补充实体完成：新增 ${generated.length} 个场景变更；按 subjects_json 增量导入 ${importResult.created} 条（跳过已存在 ${importResult.skipped} 条）。${(sceneRegenSubjectResult.summary_lines || []).join('；')}`),
                    ((Boolean(result?.entity_only_mode || sceneRegenEntityOnlyMode))
                        ? `Entity supplement completed (Entity-only mode): scene/shots unchanged; applied the markdown row patch back to the current scene and corrected environment anchor, linked characters, key props, and core scene fields when needed; created ${importResult.created} entities from subjects_json and reused/skipped ${importResult.skipped}. ${(sceneRegenSubjectResult.summary_lines || []).join('; ')}`
                        : `Entity supplement completed: applied ${generated.length} scene change(s); incrementally created ${importResult.created} subject entities from subjects_json and reused/skipped ${importResult.skipped} existing subjects. ${(sceneRegenSubjectResult.summary_lines || []).join('; ')}`)
                ),
                'success'
            );
            showSceneRegenImportSummaryAlert(sceneRegenSubjectResult, {
                isReimport: false,
                generatedSceneCount: Number(generated.length || 0),
            });
        } catch (e) {
            const status = Number(e?.response?.status || 0);
            const detail = e?.response?.data?.detail || e?.message || t('重生成失败', 'Regeneration failed');
            setSceneRegenProgress({
                phase: 'failed',
                percent: 100,
                message: t('重生成失败。', 'Regeneration failed.'),
                error: String(detail || ''),
            });

            if (status === 404) {
                onLog?.(
                    t('场景不存在或后端未包含该接口（/scenes/{id}/regenerate）。请刷新场景列表并确认后端已部署最新版本。', 'Scene not found or backend route /scenes/{id}/regenerate is unavailable. Refresh scenes and ensure backend is up-to-date.'),
                    'warning'
                );
                if (activeEpisode?.id) {
                    try {
                        const latestScenes = await fetchScenes(activeEpisode.id);
                        setScenes((latestScenes || []).map((scene) => ({
                            ...scene,
                            original_script_text: normalizeOriginalScriptText(scene?.original_script_text),
                        })));
                        const stillExists = (latestScenes || []).find((s) => s.id === editingScene?.id);
                        if (!stillExists) {
                            setEditingScene(null);
                        }
                    } catch {
                        // ignore refresh failure
                    }
                }
                alert(t('补充实体失败：目标场景不存在或后端接口不可用。已尝试刷新场景列表。', 'Entity supplement failed: target scene not found or backend route unavailable. Scene list refresh attempted.'));
            } else {
                onLog?.(`${t('补充实体失败', 'Entity supplement failed')}: ${detail}`, 'error');
                alert(`${t('补充实体失败：', 'Entity supplement failed: ')}${detail}`);
            }
        } finally {
            setSceneRegenerating(false);
        }
    };

    const pollBatchAiShotsStatus = useCallback(async () => {
        if (!activeEpisode?.id) return null;
        try {
            const status = await getSceneAiShotsBatchStatus(activeEpisode.id);
            if (!status || typeof status !== 'object') return null;
            const prevProgress = batchAiShotsProgressRef.current || createBatchAiShotsProgressState();

            const nowMs = Date.now();
            const isTransientIdle = !Boolean(status.running) && Number(status.total || 0) <= 0;
            const withinStartupGuard = nowMs < Number(batchAiShotsStartupGuardUntilRef.current || 0);
            if (isTransientIdle && withinStartupGuard) {
                return {
                    ...status,
                    running: true,
                    total: Number(prevProgress.total || 0),
                    completed: Number(prevProgress.completed || 0),
                    success: Number(prevProgress.success || 0),
                    failed: Number(prevProgress.failed || 0),
                    message: status.message || prevProgress.message || t('批量任务启动中...', 'Batch task is starting...'),
                };
            }

            setBatchAiShotsProgress(prev => ({
                ...prev,
                running: Boolean(status.running),
                total: Number(status.total || 0),
                completed: Number(status.completed || 0),
                success: Number(status.success || 0),
                failed: Number(status.failed || 0),
                stopRequested: Boolean(status.stop_requested),
                currentSceneLabel: status.current_scene_label || '',
                message: status.message || prev.message || '',
                errors: Array.isArray(status.errors) ? status.errors : [],
            }));

            if (!status.running && batchAiShotsStatusTimerRef.current) {
                clearInterval(batchAiShotsStatusTimerRef.current);
                batchAiShotsStatusTimerRef.current = null;
            }

            return status;
        } catch (e) {
            return null;
        }
    }, [activeEpisode?.id, onSwitchToShots, t]);

    useEffect(() => {
        if (!activeEpisode?.id) {
            if (batchAiShotsStatusTimerRef.current) {
                clearInterval(batchAiShotsStatusTimerRef.current);
                batchAiShotsStatusTimerRef.current = null;
            }
            return;
        }
        let cancelled = false;

        const hydrate = async () => {
            // Task pool is the source of truth when local runtime is stale after tab/page switch.
            let recovered = false;
            if (!batchAiShotsProgressRef.current?.running) {
                recovered = await recoverBatchAiShotsFromJobPool();
            }

            const status = await pollBatchAiShotsStatus();
            if (cancelled || !status) return;

            const shouldKeepPolling = Boolean(status?.running)
                || Boolean(batchAiShotsProgressRef.current?.running)
                || Boolean(recovered);

            if (shouldKeepPolling && !batchAiShotsStatusTimerRef.current) {
                batchAiShotsStatusTimerRef.current = setInterval(pollBatchAiShotsStatus, 3000);
            }

            if (!shouldKeepPolling && batchAiShotsStatusTimerRef.current) {
                clearInterval(batchAiShotsStatusTimerRef.current);
                batchAiShotsStatusTimerRef.current = null;
            }
        };

        hydrate();
        return () => {
            cancelled = true;
            if (batchAiShotsStatusTimerRef.current) {
                clearInterval(batchAiShotsStatusTimerRef.current);
                batchAiShotsStatusTimerRef.current = null;
            }
        };
    }, [activeEpisode?.id, pollBatchAiShotsStatus, recoverBatchAiShotsFromJobPool]);

    const handleStopBatchAiShots = async () => {
        if (!activeEpisode?.id) return;
        setIsStoppingBatchAiShots(true);
        try {
            const res = await stopSceneAiShotsBatch(activeEpisode.id);
            setBatchAiShotsProgress((prev) => ({
                ...prev,
                stopRequested: true,
                message: res?.message || prev.message || t('已强制停止当前场景批处理。', 'Current scene batch force-stopped.'),
            }));
            await pollBatchAiShotsStatus();
            onLog?.(`SceneManager: Batch AI Shots ${res?.message || 'stop requested'}.`, 'warning');
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'stop failed';
            onLog?.(`SceneManager: Failed to stop batch AI Shots - ${detail}`, 'error');
            alert(`Failed to stop batch AI Shots: ${detail}`);
        } finally {
            setIsStoppingBatchAiShots(false);
        }
    };

    const runBatchGenerateAiShotsForAllScenes = async () => {
        const allScenes = Array.isArray(scenes) ? scenes : [];
        const targets = allScenes.filter((scene) => !!scene?.id);
        const skipped = allScenes.length - targets.length;

        if (targets.length === 0) {
            alert(t('没有可执行 AI Shots 的已保存场景。', 'No saved scenes available for AI Shots batch run.'));
            return;
        }

        const confirmText = t(
            `确认后台批量执行 AI Shots？将处理 ${targets.length} 个场景${skipped > 0 ? `（跳过 ${skipped} 个未保存场景）` : ''}。`,
            `Run AI Shots in background for ${targets.length} scenes${skipped > 0 ? ` (skip ${skipped} unsaved scenes)` : ''}?`
        );
        if (!await confirmUiMessage(confirmText)) return;

        try {
            const started = await startSceneAiShotsBatch(activeEpisode.id, {
                scene_ids: targets.map((s) => s.id),
            });
            batchAiShotsStartupGuardUntilRef.current = Date.now() + 12000;
            batchAiShotsBootstrapUntilRef.current = Date.now() + 15000;
            setBatchAiShotsProgress((prev) => ({
                ...prev,
                running: true,
                total: Number(started?.total || targets.length),
                completed: Number(started?.completed || 0),
                success: Number(started?.success || 0),
                failed: Number(started?.failed || 0),
                stopRequested: Boolean(started?.stop_requested),
                currentSceneLabel: started?.current_scene_label || '',
                message: started?.message || t('批量任务已启动...', 'Batch task started...'),
                errors: Array.isArray(started?.errors) ? started.errors : [],
            }));
            onLog?.(`SceneManager: Batch AI Shots started. total=${targets.length}, skipped_unsaved=${skipped}`, 'info');

            if (batchAiShotsStatusTimerRef.current) {
                clearInterval(batchAiShotsStatusTimerRef.current);
                batchAiShotsStatusTimerRef.current = null;
            }
            batchAiShotsStatusTimerRef.current = setInterval(pollBatchAiShotsStatus, 3000);
            pollBatchAiShotsStatus();
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'Batch start failed';
            onLog?.(`SceneManager: Failed to start batch AI Shots - ${detail}`, 'error');
            alert(`Failed to start batch AI Shots: ${detail}`);
        }
    };

    const deleteSceneBatch = async (targetScenes, modeLabel = 'selected') => {
        const targets = Array.isArray(targetScenes) ? targetScenes : [];
        if (targets.length === 0) return;

        const confirmText = modeLabel === 'filtered'
            ? t(`确认删除当前筛选的 ${targets.length} 个场景？`, `Delete all ${targets.length} currently filtered scenes?`)
            : t(`确认删除已选中的 ${targets.length} 个场景？`, `Delete ${targets.length} selected scenes?`);
        if (!await confirmUiMessage(confirmText)) return;

        const deletableKeys = new Set();
        const failedLabels = [];

        for (const scene of targets) {
            const key = getSceneSelectionKey(scene);
            const label = scene?.scene_no || scene?.scene_name || (scene?.id ? `#${scene.id}` : t('未命名场景', 'Untitled Scene'));
            if (!scene?.id) {
                deletableKeys.add(key);
                continue;
            }
            try {
                await deleteScene(scene.id);
                deletableKeys.add(key);
            } catch (e) {
                failedLabels.push(`${label}: ${e?.response?.data?.detail || e?.message || 'delete failed'}`);
            }
        }

        if (deletableKeys.size === 0 && failedLabels.length > 0) {
            onLog?.(t('批量删除失败。', 'Bulk delete failed.'), 'error');
            alert(failedLabels.slice(0, 5).join('\n'));
            return;
        }

        const remaining = (scenes || []).filter((scene) => !deletableKeys.has(getSceneSelectionKey(scene)));
        setScenes(remaining);
        setSelectedSceneKeys((prev) => prev.filter((key) => !deletableKeys.has(key)));

        if (editingScene && deletableKeys.has(getSceneSelectionKey(editingScene))) {
            setEditingScene(null);
        }

        if (activeEpisode?.id) {
            try {
                await updateEpisode(activeEpisode.id, { scene_content: buildSceneContentMarkdown(remaining) });
            } catch (e) {
                console.warn('Failed to sync scene_content after batch delete', e);
            }
        }

        onLog?.(
            t(`批量删除完成：删除 ${deletableKeys.size} 个场景。`, `Bulk delete completed: removed ${deletableKeys.size} scenes.`),
            'success'
        );

        if (failedLabels.length > 0) {
            onLog?.(t(`有 ${failedLabels.length} 个场景删除失败。`, `${failedLabels.length} scenes failed to delete.`), 'warning');
            alert(failedLabels.slice(0, 5).join('\n'));
        }
    };

    const handleDeleteSelectedScenes = async () => {
        const targets = (filteredScenes || []).filter((scene) => selectedSceneKeySet.has(getSceneSelectionKey(scene)));
        await deleteSceneBatch(targets, 'selected');
    };

    const handleDeleteFilteredScenes = async () => {
        await deleteSceneBatch(filteredScenes || [], 'filtered');
    };

    const loadLatestAIShotsStaging = async (sceneId) => {
        if (!sceneId) {
            setAiShotsStaging(prev => ({
                ...prev,
                sceneId: null,
                content: [],
                rawText: '',
                usage: null,
                timestamp: null,
                error: null,
                loading: false,
            }));
            setShotSupplementImportReport(null);
            return;
        }

        setAiShotsStaging(prev => ({
            ...prev,
            loading: true,
            error: null,
            sceneId,
        }));
        setShotSupplementImportReport(null);

        try {
            const latest = await getSceneLatestAIResult(sceneId);
            setAiShotsStaging(prev => ({
                ...prev,
                loading: false,
                sceneId,
                content: Array.isArray(latest?.content) ? latest.content : [],
                rawText: latest?.raw_text || '',
                usage: latest?.usage || null,
                timestamp: latest?.timestamp || null,
                warnings: Array.isArray(latest?.warnings) ? latest.warnings : [],
            }));
        } catch (e) {
            console.error(e);
            // If there's no staging yet, treat as empty (avoid blocking UX)
            const status = e?.response?.status;
            if (status === 404) {
                setAiShotsStaging(prev => ({
                    ...prev,
                    loading: false,
                    sceneId,
                    content: [],
                    rawText: '',
                    usage: null,
                    timestamp: null,
                    warnings: [],
                    error: null,
                }));
                return;
            }
            setAiShotsStaging(prev => ({
                ...prev,
                loading: false,
                error: e?.response?.data?.detail || e?.message || 'Failed to load latest AI shots result',
            }));
        }
    };

    useEffect(() => {
        if (editingScene?.id) {
            loadLatestAIShotsStaging(editingScene.id);
        } else {
            // Reset when closing or opening an unsaved scene
            setAiShotsStaging(prev => ({
                ...prev,
                loading: false,
                sceneId: null,
                content: [],
                rawText: '',
                usage: null,
                timestamp: null,
                warnings: [],
                error: null,
                saving: false,
                applying: false,
            }));
            setShotSupplementImportReport(null);
            setAiShotRowEditor({ open: false, index: -1, data: null });
        }
    }, [editingScene?.id]);

    useEffect(() => {
        if (!pendingShotSupplementSceneId) return;
        if (!editingScene?.id || Number(editingScene.id) !== Number(pendingShotSupplementSceneId)) return;
        if (aiShotsStaging.loading) return;

        if (Array.isArray(aiShotsStaging.content) && aiShotsStaging.content.length > 0) {
            openShotRegenModal();
        } else {
            alert(t('当前场景还没有可补充的 AI 镜头暂存内容。请先生成 AI 镜头。', 'This scene has no staged AI shots to supplement yet. Generate AI shots first.'));
        }
        setPendingShotSupplementSceneId(null);
    }, [pendingShotSupplementSceneId, editingScene?.id, aiShotsStaging.loading, aiShotsStaging.content]);

        const handleConfirmGenerateShots = async () => {
            const { sceneId, data } = shotPromptModal;
            if (!sceneId || isSceneAiShotsGenerating(sceneId)) return;
            if (!await confirmUiMessage("This will overwrite existing shots for this scene. Continue?")) {
               setShotPromptModal(prev => ({ ...prev, loading: false }));
               return;
            }

         setShotPromptModal(prev => ({ ...prev, loading: true }));
         await executeGenerateShots({ sceneId, promptData: data });
    };

    const batchAiShotsCurrentOrdinal = (() => {
        const total = Number(batchAiShotsProgress?.total || 0);
        const completed = Number(batchAiShotsProgress?.completed || 0);
        if (total <= 0) return 0;
        if (batchAiShotsProgress?.running) {
            return Math.max(1, Math.min(total, completed + 1));
        }
        return Math.max(0, Math.min(total, completed));
    })();
    const batchAiShotsProgressSummary = (() => {
        const total = Number(batchAiShotsProgress?.total || 0);
        if (total <= 0) return '';
        const sceneSuffix = batchAiShotsProgress.currentSceneLabel
            ? t(`（场景 ${batchAiShotsProgress.currentSceneLabel}）`, ` (Scene ${batchAiShotsProgress.currentSceneLabel})`)
            : '';
        if (batchAiShotsProgress?.running) {
            return t(
                `共 ${total} 个，正在处理第 ${batchAiShotsCurrentOrdinal} 个${sceneSuffix}`,
                `Total ${total}, processing #${batchAiShotsCurrentOrdinal}${sceneSuffix}`
            );
        }
        return t(
            `共 ${total} 个，已处理 ${Number(batchAiShotsProgress?.completed || 0)} 个${sceneSuffix}`,
            `Total ${total}, processed ${Number(batchAiShotsProgress?.completed || 0)}${sceneSuffix}`
        );
    })();
    const isSceneBatchCompleted = !Boolean(batchAiShotsProgress?.running)
        && Number(batchAiShotsProgress?.total || 0) > 0
        && Number(batchAiShotsProgress?.completed || 0) >= Number(batchAiShotsProgress?.total || 0);
    const shouldShowSceneBatchProgressBanner = (batchAiShotsProgress.running || batchAiShotsProgress.total > 0)
        && (!isSceneBatchProgressDismissed || !isSceneBatchCompleted);

    useEffect(() => {
        setIsSceneBatchProgressDismissed(false);
    }, [activeEpisode?.id]);

    if (!activeEpisode) return <div className="p-6 text-muted-foreground">{t('请选择分集以管理场景。', 'Select an episode to manage scenes.')}</div>;

    return (
        <div className="p-4 sm:p-8 h-full flex flex-col w-full max-w-full overflow-hidden">
             <div className="flex justify-between items-center mb-6 shrink-0">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                    {t('场景', 'Scenes')}
                    <span className="text-sm font-normal text-muted-foreground bg-white/5 px-2 py-0.5 rounded-full">{filteredScenes.length}/{scenes.length} {t('场景', 'Scenes')}</span>
                </h2>
                <div className="flex gap-2">
                    <button
                        onClick={runBatchGenerateAiShotsForAllScenes}
                        disabled={batchAiShotsProgress.running || scenes.length === 0 || isStoppingBatchAiShots}
                        className="px-4 py-2 bg-blue-600/90 text-white rounded-lg text-sm font-bold hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        title={t('后台批量对当前分集所有场景执行 AI Shots 并自动导入', 'Run AI Shots in background for all scenes in this episode and auto-apply')}
                    >
                        {batchAiShotsProgress.running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                        {batchAiShotsProgress.running ? t('执行中...', 'Running...') : t('AI Shots', 'AI Shots')}
                    </button>
                    <button
                        onClick={handleStopBatchAiShots}
                        disabled={!batchAiShotsProgress.running || isStoppingBatchAiShots || batchAiShotsProgress.stopRequested}
                        className="px-4 py-2 bg-white/10 text-white rounded-lg text-sm font-bold hover:bg-white/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        title={t('强制停止当前后台批量 AI Shots 任务（立即生效）', 'Force stop current background batch AI Shots task (immediate)')}
                    >
                        {isStoppingBatchAiShots ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
                        {isStoppingBatchAiShots
                            ? t('停止中...', 'Stopping...')
                            : (batchAiShotsProgress.stopRequested ? t('已请求停止', 'Stop Requested') : t('停止', 'Stop'))}
                    </button>
                     <button onClick={handleSave} className="px-4 py-2 bg-primary text-black rounded-lg text-sm font-bold hover:bg-primary/90 flex items-center gap-2">
                        <CheckCircle className="w-4 h-4" />
                        {t('保存修改', 'Save Changes')}
                     </button>
                </div>
            </div>

            {shouldShowSceneBatchProgressBanner && (
                <div className={`mb-4 rounded-lg border px-4 py-2.5 flex items-center gap-2 text-sm shrink-0 ${
                    batchAiShotsProgress.running
                        ? 'border-blue-500/30 bg-blue-500/10 text-blue-100'
                        : batchAiShotsProgress.failed > 0
                            ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-100'
                            : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                }`}>
                    {batchAiShotsProgress.running ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                    <div className="flex items-center justify-between w-full gap-3">
                        <span>
                            {batchAiShotsProgress.message}
                            {batchAiShotsProgress.stopRequested ? ` · ${t('已请求停止', 'Stop requested')}` : ''}
                            {batchAiShotsProgressSummary ? ` · ${batchAiShotsProgressSummary}` : ''}
                        </span>
                        {isSceneBatchCompleted && (
                            <button
                                onClick={() => setIsSceneBatchProgressDismissed(true)}
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

            <div className="mb-3 shrink-0 rounded-xl border border-white/10 bg-black/25 p-2.5 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                        <button
                            onClick={() => setSceneSortMode('updated_desc')}
                            className={`h-7 w-7 inline-flex items-center justify-center rounded border ${sceneSortMode === 'updated_desc' ? 'bg-primary/20 text-primary border-primary/30' : 'bg-white/5 text-white border-white/10 hover:bg-white/10'}`}
                            title={t('按修改时间排序', 'Sort by modified time')}
                            aria-label={t('按修改时间排序', 'Sort by modified time')}
                        >
                            <RefreshCw className="w-3.5 h-3.5" />
                        </button>
                        <button
                            onClick={() => setSceneSortMode('hierarchy')}
                            className={`h-7 w-7 inline-flex items-center justify-center rounded border ${sceneSortMode === 'hierarchy' ? 'bg-primary/20 text-primary border-primary/30' : 'bg-white/5 text-white border-white/10 hover:bg-white/10'}`}
                            title={t('按集/场景/镜头排序', 'Sort by episode/scene/shot')}
                            aria-label={t('按集/场景/镜头排序', 'Sort by episode/scene/shot')}
                        >
                            <LayoutList className="w-3.5 h-3.5" />
                        </button>
                        <button
                            onClick={() => setSceneSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))}
                            className="h-7 w-7 inline-flex items-center justify-center rounded border bg-white/5 text-white border-white/10 hover:bg-white/10"
                            title={sceneSortDirection === 'asc' ? t('当前升序，点击切换为降序', 'Currently ascending, click to switch to descending') : t('当前降序，点击切换为升序', 'Currently descending, click to switch to ascending')}
                            aria-label={sceneSortDirection === 'asc' ? t('切换到降序', 'Switch to descending') : t('切换到升序', 'Switch to ascending')}
                        >
                            <ArrowUp className={`w-3.5 h-3.5 transition-transform ${sceneSortDirection === 'asc' ? '' : 'rotate-180'}`} />
                        </button>
                        <button
                            onClick={toggleSelectAllFiltered}
                            disabled={filteredScenes.length === 0}
                            className="h-7 w-7 inline-flex items-center justify-center rounded border bg-white/5 text-white border-white/10 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
                            title={allFilteredSelected ? t('取消全选', 'Deselect all') : t('全选', 'Select all')}
                            aria-label={allFilteredSelected ? t('取消全选', 'Deselect all') : t('全选', 'Select all')}
                        >
                            {allFilteredSelected ? <CheckSquare className="w-3.5 h-3.5" /> : <Square className="w-3.5 h-3.5" />}
                        </button>
                    </div>

                    <div className="text-[11px] text-muted-foreground px-2 py-1 rounded border border-white/10 bg-white/5">
                        {filteredScenes.length}
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5">
                        <div className="text-[11px] text-muted-foreground px-2 py-1 rounded border border-white/10 bg-white/5">
                            {selectedFilteredCount}/{filteredScenes.length}
                        </div>
                        <button
                            onClick={handleDeleteSelectedScenes}
                            disabled={selectedFilteredCount === 0}
                            className="px-2.5 py-1.5 bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 rounded text-xs text-red-200 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {t('删除已选', 'Delete Selected')}
                        </button>

                        <button
                            onClick={handleDeleteFilteredScenes}
                            disabled={filteredScenes.length === 0}
                            className="px-2.5 py-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded text-xs text-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {t('删除当前筛选全部', 'Delete All Filtered')}
                        </button>
                    </div>
                </div>
            </div>

            {aiShotsFlowStatus.phase !== 'idle' && (
                <div className={`mb-4 rounded-lg border px-4 py-2.5 flex items-center gap-2 text-sm shrink-0 ${
                    aiShotsFlowStatus.phase === 'failed'
                        ? 'border-red-500/30 bg-red-500/10 text-red-200'
                        : aiShotsFlowStatus.phase === 'completed'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                            : 'border-primary/30 bg-primary/10 text-primary'
                }`}>
                    {aiShotsFlowStatus.phase === 'completed' ? (
                        <CheckCircle className="w-4 h-4" />
                    ) : aiShotsFlowStatus.phase === 'failed' ? (
                        <X className="w-4 h-4" />
                    ) : (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    )}
                    <span>{aiShotsFlowStatus.message}</span>
                </div>
            )}

            <div className="flex-1 overflow-auto custom-scrollbar pb-20">
                    {sceneListLoading && filteredScenes.length === 0 ? (
                    <div className="space-y-4">
                        <div className="flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            {t('场景加载中...', 'Loading scenes...')}
                        </div>
                        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
                            {Array.from({ length: 6 }).map((_, idx) => (
                                <div key={`scene-skeleton-${idx}`} className="border border-white/10 rounded-lg p-4 bg-white/[0.02] animate-pulse">
                                    <div className="h-4 bg-white/10 rounded w-1/3 mb-3" />
                                    <div className="h-3 bg-white/10 rounded w-full mb-2" />
                                    <div className="h-3 bg-white/10 rounded w-5/6 mb-2" />
                                    <div className="h-3 bg-white/10 rounded w-2/3" />
                                </div>
                            ))}
                        </div>
                    </div>
                    ) : filteredScenes.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                        <Clapperboard className="w-12 h-12 mb-4 opacity-20" />
                        <p>{t('未找到场景。', 'No scenes found.')}</p>
                        <p className="text-xs mt-2 opacity-50">{t('可在导入中粘贴 Markdown 表格，或先生成内容。', 'Paste a Markdown table in Import or generate content.')}</p>
                    </div>
                    ) : (
                    <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
                        {filteredScenes.map((scene, idx) => {
                            const sceneKey = getSceneSelectionKey(scene);
                            return (
                                <SceneCard 
                                    key={idx} 
                                    scene={scene} 
                                    entities={entities} 
                                    subjectGap={sceneSubjectGapMap.get(getSceneSubjectStatusKey(scene)) || null}
                                    supplementingSubjects={Boolean(sceneSubjectSupplementingMap[getSceneSubjectStatusKey(scene)])}
                                    shotCount={Number(sceneShotCountMap?.[Number(scene?.id || 0)] || 0)}
                                    uiLang={uiLang}
                                    generatingShots={isSceneAiShotsBusy(scene?.id)}
                                    selected={selectedSceneKeySet.has(sceneKey)}
                                    onToggleSelect={toggleSceneSelected}
                                    onClick={() => setEditingScene(scene)} 
                                    onGenerateShots={handleGenerateShots}
                                    onSupplementShots={handleOpenShotSupplementMenu}
                                    onSupplementSubjects={handleSupplementSceneSubjects}
                                    onDelete={handleDeleteScene}
                                />
                            );
                        })}
                    </div>
                    )}
            </div>
            
            <AnimatePresence>
                {editingScene && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm" onClick={() => { void closeEditingScene(); }}>
                        <motion.div 
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            onClick={e => e.stopPropagation()}
                            className="bg-[#09090b] border border-white/10 rounded-xl w-full max-w-5xl h-[90vh] shadow-2xl flex flex-col overflow-hidden"
                        >
                             <div className="p-4 border-b border-white/10 flex items-center justify-between bg-[#09090b]">
                                <h3 className="font-bold text-lg">{t('编辑场景', 'Edit Scene')} {editingScene.scene_no || editingScene.id}</h3>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => handleDeleteScene(editingScene)}
                                        disabled={!editingScene?.id}
                                        className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/20 rounded text-xs flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                        title={editingScene?.id ? t('删除该场景', 'Delete this scene') : t('请先保存场景', 'Save scene first')}
                                    >
                                        <Trash2 className="w-3 h-3"/> {t('删除', 'Delete')}
                                    </button>
                                    <button
                                        onClick={() => { void handleRegenerateScene(); }}
                                        disabled={!editingScene?.id || sceneRegenerating}
                                        className="px-3 py-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/20 rounded text-xs flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                        title={editingScene?.id ? t('按要求补充当前场景缺失实体', 'Supplement missing entities for current scene') : t('请先保存场景', 'Save scene first')}
                                    >
                                        {sceneRegenerating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3"/>}
                                        {sceneRegenerating ? t('补充中...', 'Supplementing...') : t('补充实体', 'Supplement Entities')}
                                    </button>
                                    <button
                                        onClick={() => editingScene?.id && handleGenerateShots(editingScene.id)}
                                        disabled={!editingScene?.id || isSceneAiShotsBusy(editingScene?.id)}
                                        className="px-3 py-1.5 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/20 rounded text-xs flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                        title={editingScene?.id ? t('为该场景生成 AI 镜头', 'Generate AI shots for this scene') : t('请先保存场景再生成 AI 镜头', 'Save scene first to generate AI shots')}
                                    >
                                        {isSceneAiShotsBusy(editingScene?.id) ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>} {isSceneAiShotsBusy(editingScene?.id) ? t('生成中...', 'Generating...') : 'AI Shots'}
                                    </button>
                                    <button
                                        onClick={() => {
                                            if (!editingScene?.id) return;
                                            if (typeof onSwitchToShots === 'function') {
                                                onSwitchToShots(editingScene.id);
                                            }
                                            void closeEditingScene();
                                        }}
                                        disabled={!editingScene?.id}
                                        className="px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 border border-emerald-500/20 rounded text-xs flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                        title={editingScene?.id ? t('跳转到 Shots 并筛选当前场景', 'Go to Shots and filter by this scene') : t('请先保存场景', 'Save scene first')}
                                    >
                                        <Film className="w-3 h-3"/> {t('查看本场景 Shots', 'View Scene Shots')}
                                    </button>
                                    <button onClick={() => { void closeEditingScene(); }} className="p-2 hover:bg-white/10 rounded-full"><X className="w-5 h-5"/></button>
                                </div>
                            </div>
                            
                            <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
                                <div className="space-y-6">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-4">
                                            <div className="grid grid-cols-2 gap-4">
                                                <InputGroup label={t('场次号', 'Scene No')} value={editingScene.scene_no || editingScene.id} onChange={v => handleSceneUpdate({...editingScene, scene_no: v})} />
                                                <InputGroup label={t('时长', 'Duration')} value={editingScene.equivalent_duration} onChange={v => handleSceneUpdate({...editingScene, equivalent_duration: v})} />
                                            </div>
                                                <InputGroup label={t('场景名称', 'Scene Name')} value={editingScene.scene_name} onChange={v => handleSceneUpdate({...editingScene, scene_name: v})} />
                                                <InputGroup label={t('环境锚点', 'Environment Anchor')} value={editingScene.environment_name} onChange={v => handleSceneUpdate({...editingScene, environment_name: v})} />
                                                <InputGroup label={t('关联角色（逗号分隔）', 'Linked Characters (Comma separated)')} value={editingScene.linked_characters} onChange={v => handleSceneUpdate({...editingScene, linked_characters: v})} />
                                                <InputGroup label={t('关键道具', 'Key Props')} value={editingScene.key_props} onChange={v => handleSceneUpdate({...editingScene, key_props: v})} />
                                        </div>

                                        <div className="flex flex-col h-full"> 
                                            <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-2 block">{t('原始剧本文本', 'Original Script Text')}</label>
                                            <MarkdownCell value={editingScene.original_script_text} onChange={v => handleSceneUpdate({...editingScene, original_script_text: v})} className="flex-1 min-h-[200px]" />
                                        </div>
                                    </div>
                                    
                                    <div className="pt-4 border-t border-white/5 h-full flex flex-col">
                                         <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-2 block text-amber-300/90">{t('补充要求', 'Supplement Requirements')}</label>
                                         <textarea
                                            className="w-full bg-black/40 border border-amber-500/20 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-amber-400/60 resize-y custom-scrollbar leading-relaxed min-h-[96px] mb-4"
                                            value={sceneRegenRequirements}
                                            onChange={e => setSceneRegenRequirements(e.target.value)}
                                                          placeholder={t('可留空，默认“补充所缺实体”；也可输入例如：补上缺失角色/服装版本/环境变体/关键道具，并说明命名或锚点要求。', 'Optional. If empty, defaults to "Supplement missing entities"; you can also specify: add missing characters / outfit variants / environment variants / key props, and clarify naming or anchor requirements.')}
                                        />
                                        <label className="mb-3 inline-flex items-center gap-2 text-xs text-white/80 select-none">
                                            <input
                                                type="checkbox"
                                                className="h-3.5 w-3.5"
                                                checked={sceneRegenEntityOnlyMode}
                                                onChange={(e) => setSceneRegenEntityOnlyMode(Boolean(e.target.checked))}
                                                disabled={sceneRegenerating}
                                            />
                                            <span>
                                                {t('仅补实体（默认）：注入项目信息、现有 subjects、当前场景内容与补充要求；不替换场景、不删除分镜；仅补缺失实体并按需更新环境锚点/关联角色/关键道具', 'Entity-only (default): inject project context, existing subjects, current scene content, and supplement requirements; keep scene/shots unchanged; only fill missing entities and patch environment anchor / linked characters / key props when needed')}
                                            </span>
                                        </label>
                                        {(sceneRegenerating || sceneRegenReimporting || sceneRegenScenePatching || sceneRegenProgress.phase === 'reimport_subjects_json' || sceneRegenProgress.phase === 'rebuild_scenes_from_raw' || sceneRegenProgress.phase === 'done' || sceneRegenProgress.phase === 'failed') && (
                                            <div className={`mb-4 rounded border p-3 ${
                                                sceneRegenProgress.phase === 'failed'
                                                    ? 'border-red-500/30 bg-red-500/10'
                                                    : 'border-amber-500/30 bg-amber-500/10'
                                            }`}>
                                                <div className="flex items-center justify-between text-[11px] font-semibold mb-2">
                                                    <span>
                                                        {sceneRegenProgress.message || t('正在处理...', 'Processing...')}
                                                    </span>
                                                    <span>{Math.max(0, Math.min(100, Number(sceneRegenProgress.percent || 0)))}%</span>
                                                </div>
                                                <div className="h-1.5 w-full rounded bg-white/10 overflow-hidden">
                                                    <div
                                                        className={`h-full transition-all duration-300 ${sceneRegenProgress.phase === 'failed' ? 'bg-red-400/80' : 'bg-amber-300/90'}`}
                                                        style={{ width: `${Math.max(0, Math.min(100, Number(sceneRegenProgress.percent || 0)))}%` }}
                                                    />
                                                </div>
                                                {sceneRegenProgress.error ? (
                                                    <div className="mt-2 text-[11px] text-red-200 break-words">
                                                        {sceneRegenProgress.error}
                                                    </div>
                                                ) : null}
                                            </div>
                                        )}
                                        {sceneRegenSubjectsReport && (
                                            <div className="mb-4 rounded border border-white/10 bg-black/20 p-3">
                                                <div className="flex items-center justify-between gap-2 mb-2">
                                                    <div className="text-xs font-bold uppercase tracking-wide text-white/90">
                                                        {t('补充实体结果', 'Entity Supplement Result')}
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <div className={`text-[10px] font-mono px-2 py-0.5 rounded border ${sceneRegenSubjectsReport.entity_only_mode ? 'text-sky-100 border-sky-400/40 bg-sky-500/15' : 'text-violet-100 border-violet-400/40 bg-violet-500/15'}`}>
                                                            {sceneRegenSubjectsReport.entity_only_mode
                                                                ? t('执行模式：仅补实体', 'Mode: Entity-Only')
                                                                : t('执行模式：完整替换', 'Mode: Full Replace')}
                                                        </div>
                                                        <button
                                                            onClick={() => { void handleReimportSceneRegenLlmContent(); }}
                                                            disabled={sceneRegenerating || sceneRegenReimporting || sceneRegenScenePatching}
                                                            className="px-2 py-1 rounded border border-sky-500/30 bg-sky-500/15 text-[10px] text-sky-100 hover:bg-sky-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                                            title={t('按上次重生成返回内容补实体（subjects_json）', 'Patch entities from last regenerated subjects_json')}
                                                        >
                                                            {sceneRegenReimporting ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                                                            {sceneRegenReimporting ? t('补实体中...', 'Patching Entities...') : t('补实体', 'Patch Entities')}
                                                        </button>
                                                        <button
                                                            onClick={() => { void handlePatchScenesFromRegenRawMarkdown(); }}
                                                            disabled={sceneRegenerating || sceneRegenReimporting || sceneRegenScenePatching}
                                                            className="px-2 py-1 rounded border border-violet-500/30 bg-violet-500/15 text-[10px] text-violet-100 hover:bg-violet-500/25 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                                            title={t('按上次重生成返回内容补场景（raw_markdown）', 'Patch scenes from last regenerated raw_markdown')}
                                                        >
                                                            {sceneRegenScenePatching ? <Loader2 className="w-3 h-3 animate-spin" /> : <TableIcon className="w-3 h-3" />}
                                                            {sceneRegenScenePatching ? t('补场景中...', 'Patching Scenes...') : t('补场景', 'Patch Scenes')}
                                                        </button>
                                                        <div className={`text-[10px] font-mono ${sceneRegenSubjectsReport.persisted ? 'text-emerald-300' : 'text-amber-200'}`}>
                                                            {sceneRegenSubjectsReport.persisted
                                                                ? t('已持久化保存', 'Persisted')
                                                                : t('未持久化（仅当前会话可见）', 'Not persisted (session only)')}
                                                        </div>
                                                    </div>
                                                </div>
                                                <div className="text-[11px] text-muted-foreground mb-3">
                                                    {t('新增', 'Created')}: <span className="font-mono text-white/80">{Number(sceneRegenSubjectsReport.created_count || 0)}</span>
                                                    <span className="mx-2">|</span>
                                                    {t('跳过', 'Skipped')}: <span className="font-mono text-white/80">{Number(sceneRegenSubjectsReport.skipped_count || 0)}</span>
                                                    <span className="mx-2">|</span>
                                                    subjects_json: <span className="font-mono text-white/80">{Number(sceneRegenSubjectsReport.subjects_json_count || 0)}</span>
                                                    <span className="mx-2">|</span>
                                                    {t('重导入次数', 'Re-import')}: <span className="font-mono text-white/80">{Number(sceneRegenSubjectsReport.reimport_count || 0)}</span>
                                                    <span className="mx-2">|</span>
                                                    {t('补场景', 'Patch Scenes')}: <span className="font-mono text-white/80">{Number(sceneRegenSubjectsReport?.scene_patch?.updated_count || 0)}↑/{Number(sceneRegenSubjectsReport?.scene_patch?.created_count || 0)}+</span>
                                                </div>
                                                {Array.isArray(sceneRegenSubjectsReport.summary_lines) && sceneRegenSubjectsReport.summary_lines.length > 0 && (
                                                    <div className="mb-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                                                        <div className="text-[11px] font-bold uppercase tracking-wide text-white/85 mb-1.5">
                                                            {t('补充与导入汇总', 'Supplement and Import Summary')}
                                                        </div>
                                                        <div className="space-y-1">
                                                            {sceneRegenSubjectsReport.summary_lines.map((line, idx) => (
                                                                <div key={`scene-regen-summary-${idx}`} className="text-[11px] text-white/75 leading-relaxed">
                                                                    {line}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                                    {[
                                                        { key: 'character', label: t('角色', 'Characters') },
                                                        { key: 'environment', label: t('场景', 'Environments') },
                                                        { key: 'prop', label: t('道具', 'Props') },
                                                    ].map((group) => {
                                                        const createdItems = (sceneRegenSubjectsReport.created_items || []).filter((item) => String(item?.type || '') === group.key);
                                                        const skippedItems = (sceneRegenSubjectsReport.skipped_items || []).filter((item) => String(item?.type || '') === group.key);
                                                        const counts = (sceneRegenSubjectsReport.by_type && sceneRegenSubjectsReport.by_type[group.key]) || { created: 0, skipped: 0 };
                                                        return (
                                                            <div key={group.key} className="rounded-lg border border-white/10 bg-black/30 p-2.5">
                                                                <div className="flex items-center justify-between mb-1.5 text-[11px] font-bold uppercase tracking-wide text-white/90">
                                                                    <span>{group.label}</span>
                                                                    <span className="font-mono text-white/65">+{Number(counts.created || 0)} / -{Number(counts.skipped || 0)}</span>
                                                                </div>
                                                                <div className="space-y-1 max-h-32 overflow-auto custom-scrollbar pr-1">
                                                                    {createdItems.map((item, idx) => (
                                                                        <div key={`created-${group.key}-${idx}`} className="text-[11px] text-emerald-200 bg-emerald-500/10 border border-emerald-500/20 rounded px-2 py-1 truncate" title={String(item?.name || '')}>
                                                                            + {String(item?.name || '')}
                                                                        </div>
                                                                    ))}
                                                                    {skippedItems.map((item, idx) => (
                                                                        <div key={`skipped-${group.key}-${idx}`} className="text-[11px] text-white/70 bg-white/5 border border-white/10 rounded px-2 py-1 truncate" title={String(item?.name || '')}>
                                                                            = {String(item?.name || '')}
                                                                        </div>
                                                                    ))}
                                                                    {createdItems.length === 0 && skippedItems.length === 0 && (
                                                                        <div className="text-[11px] text-muted-foreground">{t('暂无', 'Empty')}</div>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                         <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-2 block text-primary/80">{t('核心场景信息（视觉指导）', 'Core Scene Info (Visual Direction)')}</label>
                                         <textarea 
                                            className="w-full flex-1 bg-black/40 border border-white/10 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-none custom-scrollbar font-mono leading-relaxed min-h-[400px]"
                                            value={editingScene.core_scene_info || ''}
                                            onChange={e => handleSceneUpdate({...editingScene, core_scene_info: e.target.value})}
                                            placeholder={t('输入视觉指导、光照、情绪、构图等...', 'Enter visual direction, lighting, mood, composition...')}
                                        />
                                    </div>

                                    <div className="pt-4 border-t border-white/5">
                                        <div className="flex items-center justify-between gap-3 mb-2">
                                            <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider block text-primary/80">{t('AI 镜头（暂存区）', 'AI Shots (Staging)')}</label>
                                            <div className="text-[10px] text-muted-foreground">双击任意行可弹窗编辑并保存更新</div>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={openShotRegenModal}
                                                    disabled={!editingScene?.id || aiShotsStaging.loading || aiShotsStaging.saving || aiShotsStaging.applying || (aiShotsStaging.content || []).length === 0}
                                                    className="px-3 py-1.5 bg-amber-600/80 hover:bg-amber-500/90 rounded-md text-xs font-bold text-white disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                                                    title={t('基于当前暂存镜头、实体描述和附加要求，生成仅包含变更/新增项的补充分镜结果', 'Generate a selective shot supplement based on current staged shots, entity descriptions, and extra instructions')}
                                                >
                                                    <Sparkles className="w-3 h-3" />
                                                    {t('补充分镜', 'Supplement Shots')}
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        if (!editingScene?.id) return;
                                                        loadLatestAIShotsStaging(editingScene.id);
                                                    }}
                                                    disabled={!editingScene?.id || aiShotsStaging.loading || aiShotsStaging.saving || aiShotsStaging.applying}
                                                    className="px-3 py-1.5 bg-sky-700/70 hover:bg-sky-600/80 rounded-md text-xs font-bold text-white disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                                                    title={t('重新读取该场景最新的 AI 镜头 Markdown/暂存内容', 'Reload latest AI shots markdown/staging content for this scene')}
                                                >
                                                    {aiShotsStaging.loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                                                    {aiShotsStaging.loading ? t('刷新中…', 'Refreshing…') : t('刷新 Markdown', 'Refresh Markdown')}
                                                </button>
                                                <button
                                                    onClick={async () => {
                                                        if (!editingScene.id) return;
                                                        setAiShotsStaging(prev => ({ ...prev, saving: true }));
                                                        try {
                                                            await updateSceneLatestAIResult(editingScene.id, aiShotsStaging.content || []);
                                                            onLog?.('Staged draft saved.', 'success');
                                                        } catch (e) {
                                                            onLog?.('Failed to save draft: ' + (e?.response?.data?.detail || e?.message), 'error');
                                                        } finally {
                                                            setAiShotsStaging(prev => ({ ...prev, saving: false }));
                                                        }
                                                    }}
                                                    disabled={!editingScene.id || aiShotsStaging.saving}
                                                    className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-md text-xs font-bold text-white disabled:opacity-50"
                                                    title={t('将编辑后的暂存表保存回 scenes.ai_shots_result', 'Save the edited staging table back into scenes.ai_shots_result')}
                                                >
                                                    {aiShotsStaging.saving ? t('保存中…', 'Saving…') : t('保存草稿', 'Save Draft')}
                                                </button>
                                                <button
                                                    onClick={handleApplyAiShotsStaging}
                                                    disabled={!editingScene.id || aiShotsStaging.applying}
                                                    className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 rounded-md text-xs font-bold text-white disabled:opacity-50"
                                                    title={hasAiShotRegenMarkers
                                                        ? t('按 marker 选择性导入补充分镜结果', 'Selectively import the shot supplement result based on markers')
                                                        : t('将暂存镜头导入/应用到 shots 表', 'Import/apply the staged shots into the shots table')}
                                                >
                                                    {aiShotsStaging.applying
                                                        ? t('应用中…', 'Applying…')
                                                        : hasAiShotRegenMarkers
                                                            ? t('导入补充分镜', 'Import Supplement')
                                                            : t('应用到场景', 'Apply to Scene')}
                                                </button>
                                            </div>
                                        </div>

                                        {!editingScene.id ? (
                                            <div className="text-xs text-muted-foreground bg-white/5 border border-white/10 rounded p-3">
                                                {t('请先保存当前场景，以创建数据库记录后再加载或应用 AI 镜头。', 'Save this Scene first to create a DB record before loading or applying AI shots.')}
                                            </div>
                                        ) : aiShotsStaging.error ? (
                                            <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded p-3">
                                                {aiShotsStaging.error}
                                            </div>
                                        ) : aiShotsStaging.loading ? (
                                            <div className="flex items-center justify-center h-24"><Loader2 className="animate-spin text-primary" size={24}/></div>
                                        ) : (
                                            <>
                                                {Array.isArray(aiShotsStaging.warnings) && aiShotsStaging.warnings.length > 0 && (
                                                    <div className="text-xs text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded p-3 space-y-1 mb-3">
                                                        {aiShotsStaging.warnings.map((msg, idx) => (
                                                            <div key={`ai-shots-warning-${idx}`}>{msg}</div>
                                                        ))}
                                                    </div>
                                                )}
                                                {hasAiShotRegenMarkers && (
                                                    <div className="text-xs text-sky-100 bg-sky-500/10 border border-sky-500/20 rounded p-3 space-y-1 mb-3">
                                                        <div>{t('当前暂存区为“补充分镜”结果。', 'Current staging content is a shot supplement diff result.')}</div>
                                                        <div>{t('=更新分镜 会更新同 ID 既有镜头；=补充分镜 会新增同基准 ID 的后缀镜头。', '=更新分镜 updates an existing shot with the same ID; =补充分镜 creates a suffixed shot under the same base ID.')}</div>
                                                        <div>{t('未带 marker 的行在导入时会被跳过，不会覆盖原镜头。', 'Rows without a marker are skipped during import and will not overwrite existing shots.')}</div>
                                                    </div>
                                                )}
                                                {shotSupplementImportReport && Number(shotSupplementImportReport.scene_id || 0) === Number(editingScene?.id || 0) && (
                                                    <div className="mb-3 rounded border border-white/10 bg-black/20 p-3">
                                                        <div className="flex items-center justify-between gap-2 mb-2">
                                                            <div className="text-xs font-bold uppercase tracking-wide text-white/90">
                                                                {t('补充分镜导入汇总', 'Shot Supplement Import Summary')}
                                                            </div>
                                                            <div className="text-[10px] font-mono text-sky-100 border border-sky-500/25 bg-sky-500/10 rounded px-2 py-0.5">
                                                                {t('选择性导入', 'Selective Import')}
                                                            </div>
                                                        </div>
                                                        <div className="text-[11px] text-muted-foreground mb-3">
                                                            {t('更新', 'Updated')}: <span className="font-mono text-white/80">{Number(shotSupplementImportReport.updated_count || 0)}</span>
                                                            <span className="mx-2">|</span>
                                                            {t('新增', 'Created')}: <span className="font-mono text-white/80">{Number(shotSupplementImportReport.created_count || 0)}</span>
                                                            <span className="mx-2">|</span>
                                                            {t('跳过', 'Skipped')}: <span className="font-mono text-white/80">{Number(shotSupplementImportReport.skipped_count || 0)}</span>
                                                        </div>
                                                        {Array.isArray(shotSupplementImportReport.summary_lines) && shotSupplementImportReport.summary_lines.length > 0 && (
                                                            <div className="mb-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                                                                <div className="text-[11px] font-bold uppercase tracking-wide text-white/85 mb-1.5">
                                                                    {t('执行摘要', 'Execution Summary')}
                                                                </div>
                                                                <div className="space-y-1">
                                                                    {shotSupplementImportReport.summary_lines.map((line, idx) => (
                                                                        <div key={`shot-supplement-summary-${idx}`} className="text-[11px] text-white/75 leading-relaxed">
                                                                            {line}
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                                            {[
                                                                { key: 'updated_items', label: t('已更新', 'Updated'), tone: 'emerald' },
                                                                { key: 'created_items', label: t('已新增', 'Created'), tone: 'sky' },
                                                                { key: 'skipped_items', label: t('已跳过', 'Skipped'), tone: 'white' },
                                                            ].map((group) => {
                                                                const items = Array.isArray(shotSupplementImportReport[group.key]) ? shotSupplementImportReport[group.key] : [];
                                                                const toneClass = group.tone === 'emerald'
                                                                    ? 'text-emerald-200 bg-emerald-500/10 border-emerald-500/20'
                                                                    : group.tone === 'sky'
                                                                        ? 'text-sky-100 bg-sky-500/10 border-sky-500/20'
                                                                        : 'text-white/75 bg-white/5 border-white/10';
                                                                return (
                                                                    <div key={group.key} className="rounded-lg border border-white/10 bg-black/30 p-2.5">
                                                                        <div className="flex items-center justify-between mb-1.5 text-[11px] font-bold uppercase tracking-wide text-white/90">
                                                                            <span>{group.label}</span>
                                                                            <span className="font-mono text-white/65">{items.length}</span>
                                                                        </div>
                                                                        <div className="space-y-1 max-h-40 overflow-auto custom-scrollbar pr-1">
                                                                            {items.map((item, idx) => {
                                                                                const shotId = String(item?.shot_id || '').trim();
                                                                                const shotName = String(item?.shot_name || '').trim();
                                                                                const reason = String(item?.reason || '').trim();
                                                                                return (
                                                                                    <div key={`${group.key}-${idx}`} className={`rounded border px-2 py-1.5 ${toneClass}`}>
                                                                                        <div className="text-[11px] font-mono truncate" title={shotId || shotName || reason}>
                                                                                            {shotId || t('未命名镜头', 'Unnamed Shot')}
                                                                                            {shotName ? ` · ${shotName}` : ''}
                                                                                        </div>
                                                                                        {reason ? (
                                                                                            <div className="text-[10px] leading-relaxed opacity-80 mt-0.5 break-words">
                                                                                                {reason}
                                                                                            </div>
                                                                                        ) : null}
                                                                                    </div>
                                                                                );
                                                                            })}
                                                                            {items.length === 0 && (
                                                                                <div className="text-[11px] text-muted-foreground">{t('暂无', 'Empty')}</div>
                                                                            )}
                                                                        </div>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                )}
                                        {(aiShotsStaging.content || []).length === 0 ? (
                                            <div className="text-xs text-muted-foreground bg-white/5 border border-white/10 rounded p-3">
                                                {t('暂无暂存 AI 镜头。请先为该场景生成 AI 镜头。', 'No staged AI shots yet. Generate AI shots for this scene first.')}
                                            </div>
                                        ) : (
                                            <div className="bg-black/30 border border-white/10 rounded-md overflow-hidden">
                                                <div className="md:hidden max-h-[420px] overflow-auto custom-scrollbar p-3 space-y-3">
                                                    {(aiShotsStaging.content || []).map((shot, idx) => (
                                                        <div key={`mobile-shot-${idx}`} className="bg-white/5 border border-white/10 rounded-lg p-3 space-y-2.5">
                                                            <div className="text-[11px] font-bold text-white/90 truncate">
                                                                {(shot['Shot ID'] || shot.shot_id || `#${idx + 1}`)} · {(shot['Shot Name'] || shot.shot_name || t('未命名镜头', 'Untitled Shot'))}
                                                            </div>
                                                            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{t('镜头逻辑', 'Shot Logic')}</div>
                                                            <input
                                                                className="w-full bg-black/30 border border-white/10 rounded-md px-2.5 py-2.5 text-[13px]"
                                                                value={shot['Shot Logic (CN)'] || shot.shot_logic_cn || ''}
                                                                onChange={e => {
                                                                    const newData = [...(aiShotsStaging.content || [])];
                                                                    newData[idx] = { ...shot, 'Shot Logic (CN)': e.target.value };
                                                                    setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                }}
                                                                placeholder={t('镜头逻辑', 'Shot logic')}
                                                            />
                                                            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{t('镜头内容', 'Video Content')}</div>
                                                            <textarea
                                                                className="w-full bg-black/30 border border-white/10 rounded-md px-2.5 py-2.5 text-[13px] min-h-[88px]"
                                                                value={shot['Video Content'] || shot.video_content || ''}
                                                                onChange={e => {
                                                                    const newData = [...(aiShotsStaging.content || [])];
                                                                    newData[idx] = { ...shot, 'Video Content': e.target.value };
                                                                    setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                }}
                                                                placeholder={t('镜头内容', 'Video content')}
                                                            />
                                                            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{t('视频内容（中文）', 'Video Content (CN)')}</div>
                                                            <textarea
                                                                className="w-full bg-black/30 border border-white/10 rounded-md px-2.5 py-2.5 text-[13px] min-h-[88px]"
                                                                value={shot['Video Content (CN)'] || shot.video_content_cn || shot.video_prompt_cn || shot['Prompt (CN)'] || shot.prompt_cn || ''}
                                                                onChange={e => {
                                                                    const newData = [...(aiShotsStaging.content || [])];
                                                                    newData[idx] = { ...shot, 'Video Content (CN)': e.target.value, video_prompt_cn: e.target.value };
                                                                    setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                }}
                                                                placeholder={t('视频内容中文提示词', 'Chinese video content prompt')}
                                                            />
                                                            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{t('基础字段', 'Basic Fields')}</div>
                                                            <div className="grid grid-cols-2 gap-2">
                                                                <input
                                                                    className="bg-black/30 border border-white/10 rounded-md px-2.5 py-2.5 text-[13px]"
                                                                    value={shot['Duration (s)'] || shot.duration || ''}
                                                                    onChange={e => {
                                                                        const newData = [...(aiShotsStaging.content || [])];
                                                                        newData[idx] = { ...shot, 'Duration (s)': e.target.value };
                                                                        setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                    }}
                                                                    placeholder={t('时长(s)', 'Duration(s)')}
                                                                />
                                                                <input
                                                                    className="bg-black/30 border border-white/10 rounded-md px-2.5 py-2.5 text-[13px]"
                                                                    value={shot['Shot Name'] || shot.shot_name || ''}
                                                                    onChange={e => {
                                                                        const newData = [...(aiShotsStaging.content || [])];
                                                                        newData[idx] = { ...shot, 'Shot Name': e.target.value };
                                                                        setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                    }}
                                                                    placeholder={t('镜头名', 'Shot name')}
                                                                />
                                                            </div>
                                                            <div className="grid grid-cols-2 gap-2 pt-1 border-t border-white/10">
                                                                <button
                                                                    onClick={() => openAiShotRowEditor(shot, idx)}
                                                                    className="px-2 py-2.5 rounded-md bg-white/10 hover:bg-white/20 text-[12px] font-semibold"
                                                                >
                                                                    {t('更多字段', 'More Fields')}
                                                                </button>
                                                                <button
                                                                    onClick={() => {
                                                                        const newData = (aiShotsStaging.content || []).filter((_, i) => i !== idx);
                                                                        setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                    }}
                                                                    className="px-2 py-2.5 rounded-md bg-red-500/10 hover:bg-red-500/20 text-red-200 text-[12px] font-semibold"
                                                                >
                                                                    {t('删除', 'Delete')}
                                                                </button>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                                <div className="hidden md:block max-h-[320px] overflow-auto custom-scrollbar">
                                                    <table className="w-full min-w-[1360px] text-xs text-left border-collapse">
                                                        <thead className="sticky top-0 bg-[#252525] z-10 shadow-md">
                                                            <tr>
                                                                {aiShotsStagingColumns.map((columnKey) => (
                                                                    <th key={`ai-shot-head-${columnKey}`} className="p-2 border-b border-white/10 font-bold text-white/70 whitespace-nowrap">
                                                                        {getAiShotColumnLabel(columnKey)}
                                                                    </th>
                                                                ))}
                                                                <th className="p-2 border-b border-white/10 w-10"></th>
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-white/5">
                                                            {(aiShotsStaging.content || []).map((shot, idx) => (
                                                                <tr
                                                                    key={idx}
                                                                    className="hover:bg-white/5 group cursor-pointer"
                                                                    onDoubleClick={() => openAiShotRowEditor(shot, idx)}
                                                                    title={t('双击可在弹窗中编辑该行', 'Double click to edit this row in popup')}
                                                                >
                                                                    {aiShotsStagingColumns.map((columnKey) => {
                                                                        const value = getAiShotColumnValue(shot, columnKey);
                                                                        const useTextarea = isAiShotLongTextColumn(columnKey);
                                                                        return (
                                                                            <td key={`ai-shot-cell-${idx}-${columnKey}`} className="p-1 align-top">
                                                                                {useTextarea ? (
                                                                                    <textarea
                                                                                        className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded resize-y min-h-[40px]"
                                                                                        value={value}
                                                                                        onChange={e => {
                                                                                            const newData = [...(aiShotsStaging.content || [])];
                                                                                            newData[idx] = { ...shot, [columnKey]: e.target.value };
                                                                                            setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                                        }}
                                                                                    />
                                                                                ) : (
                                                                                    <input
                                                                                        className="bg-transparent w-full focus:outline-none focus:bg-white/5 p-1 rounded"
                                                                                        value={value}
                                                                                        onChange={e => {
                                                                                            const newData = [...(aiShotsStaging.content || [])];
                                                                                            newData[idx] = { ...shot, [columnKey]: e.target.value };
                                                                                            setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                                        }}
                                                                                    />
                                                                                )}
                                                                            </td>
                                                                        );
                                                                    })}
                                                                    <td className="p-1 text-center">
                                                                        <button
                                                                            onClick={() => {
                                                                                const newData = (aiShotsStaging.content || []).filter((_, i) => i !== idx);
                                                                                setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                                            }}
                                                                            className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500"
                                                                            title={t('删除行', 'Delete row')}
                                                                        >
                                                                            <Trash2 size={14}/>
                                                                        </button>
                                                                    </td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                                <div className="p-2 border-t border-white/10 flex flex-wrap items-center justify-between gap-2">
                                                    <button
                                                        onClick={() => {
                                                            const nextIndex = (aiShotsStaging.content?.length || 0) + 1;
                                                            const newRow = {};
                                                            aiShotsStagingColumns.forEach((columnKey) => {
                                                                newRow[columnKey] = '';
                                                            });
                                                            if (Object.prototype.hasOwnProperty.call(newRow, 'Shot ID')) {
                                                                newRow['Shot ID'] = String(nextIndex);
                                                            } else {
                                                                newRow.shot_id = String(nextIndex);
                                                            }
                                                            const newData = [...(aiShotsStaging.content || []), newRow];
                                                            setAiShotsStaging(prev => ({ ...prev, content: newData }));
                                                        }}
                                                        className="w-full md:w-auto px-3 py-2 bg-white/5 hover:bg-white/10 rounded flex items-center justify-center gap-2 text-xs font-semibold"
                                                    >
                                                        <Plus size={14}/> {t('新增一行', 'Add Row')}
                                                    </button>
                                                    {(aiShotsStaging.timestamp || aiShotsStaging.usage) && (
                                                        <div className="text-[10px] text-muted-foreground">
                                                            {aiShotsStaging.timestamp ? `Updated: ${aiShotsStaging.timestamp}` : ''}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                            </>
                                        )}

                                        {editingScene.id ? (
                                            <div className="mt-3 bg-black/30 border border-white/10 rounded-md p-3">
                                                <div className="flex items-center justify-between gap-2 mb-2">
                                                    <label className="text-[11px] text-muted-foreground uppercase font-bold tracking-wide">
                                                        {t('原始 LLM Markdown（只读）', 'Raw LLM Markdown (Read-only)')}
                                                    </label>
                                                    <span className="text-[10px] text-muted-foreground">
                                                        {t('用于核对模型原始返回，不参与此处直接编辑。', 'For auditing original model output; not edited here directly.')}
                                                    </span>
                                                </div>
                                                {String(aiShotsStaging.rawText || '').trim() ? (
                                                    <textarea
                                                        readOnly
                                                        className="w-full bg-black/40 border border-white/10 rounded p-3 text-white/85 text-xs focus:outline-none resize-y custom-scrollbar font-mono leading-relaxed min-h-[260px] max-h-[72vh]"
                                                        value={String(aiShotsStaging.rawText || '')}
                                                    />
                                                ) : (
                                                    <div className="text-xs text-muted-foreground bg-white/5 border border-white/10 rounded p-3">
                                                        {t('暂无原始 Markdown 内容。可点击“刷新 Markdown”重新读取。', 'No raw markdown found. Click "Refresh Markdown" to reload.')}
                                                    </div>
                                                )}
                                            </div>
                                        ) : null}
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
            
            {shotPromptModal.open && (
                <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="p-4 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Wand2 size={16} className="text-primary"/> Generate AI Shots</h3>
                            <button onClick={closeSceneShotPromptModal}><X size={18}/></button>
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
                                onClick={closeSceneShotPromptModal}
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
                    </div>
                </div>
            )}

            {shotRegenModal.open && (
                <div className="fixed inset-0 z-[52] bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="p-4 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Sparkles size={16} className="text-amber-300" /> {t('补充分镜', 'Supplement Shots')}</h3>
                            <button onClick={() => setShotRegenModal({ open: false, sceneId: null, instructions: '', submitting: false, error: '' })} disabled={shotRegenModal.submitting}><X size={18} /></button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            <div className="bg-amber-500/10 border border-amber-500/20 rounded p-3 text-xs text-amber-100 flex items-start gap-2">
                                <Info size={14} className="shrink-0 mt-0.5" />
                                <div className="space-y-1">
                                    <div>{t('本次会复用 shot_generator.txt，并临时注入“只输出变更/新增分镜”的规则。', 'This reuses shot_generator.txt and injects temporary rules to return only changed/new shots.')}</div>
                                    <div>{t('请在下方输入你希望补充或改写的要求，例如新增镜头节奏、补拍反应镜头、增强角色动作连续性。生成完成后会自动导入到场景，并输出变化报告。', 'Enter the additional requirements below, such as adding beats, inserting reaction shots, or strengthening action continuity. After generation, the result will be auto-imported into the scene with a change report.')}</div>
                                </div>
                            </div>

                            <div className="bg-sky-500/10 border border-sky-500/20 rounded p-3 text-xs text-sky-100 space-y-1">
                                <div>{t('输出规则', 'Output rules')}</div>
                                <div>{t('1. 只返回需要修改或新增的分镜。', '1. Return only shots that need changes or additions.')}</div>
                                <div>{t('2. 修改既有分镜时保留 Shot ID，并在 Shot Logic (CN) 末尾追加 =更新分镜。', '2. Preserve Shot ID for existing shots and append =更新分镜 to Shot Logic (CN).')}</div>
                                <div>{t('3. 新增分镜时使用 _1/_2 这类后缀 Shot ID，并在 Shot Logic (CN) 末尾追加 =补充分镜。', '3. Use suffixed Shot IDs like _1/_2 for new shots and append =补充分镜 to Shot Logic (CN).')}</div>
                            </div>

                            <div className="flex flex-col gap-2">
                                <label className="text-xs font-bold text-muted-foreground uppercase">{t('补充要求', 'Additional Instructions')}</label>
                                <textarea
                                    className="bg-black/30 border border-white/10 rounded-md p-3 text-sm text-white/90 font-mono min-h-[220px] focus:outline-none focus:border-amber-300/50 resize-y"
                                    value={shotRegenModal.instructions}
                                    onChange={(e) => setShotRegenModal((prev) => ({ ...prev, instructions: e.target.value, error: '' }))}
                                    placeholder={t('例如：在冲突爆发前补一个角色对视镜头；将结尾拆成两条分镜，突出环境反应。', 'Example: add a reaction beat before the conflict; split the ending into two shots to emphasize environment response.')}
                                    disabled={shotRegenModal.submitting}
                                />
                            </div>

                            {shotRegenModal.error ? (
                                <div className="text-xs text-red-200 bg-red-500/10 border border-red-500/20 rounded p-3">
                                    {shotRegenModal.error}
                                </div>
                            ) : null}
                        </div>

                        <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                            <button
                                onClick={() => setShotRegenModal({ open: false, sceneId: null, instructions: '', submitting: false, error: '' })}
                                disabled={shotRegenModal.submitting}
                                className="px-4 py-2 rounded hover:bg-white/10 text-sm"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button
                                onClick={handleConfirmShotRegenerate}
                                disabled={shotRegenModal.submitting}
                                className="px-6 py-2 bg-amber-500 hover:bg-amber-400 text-black rounded text-sm font-medium flex items-center gap-2"
                            >
                                {shotRegenModal.submitting ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />}
                                {shotRegenModal.submitting ? t('生成并导入中...', 'Generating and Importing...') : t('生成并自动导入', 'Generate and Auto-Import')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {sceneRegenPromptModal.open && (
                <div className="fixed inset-0 z-[55] bg-black/80 flex items-center justify-center p-4">
                    <div className="bg-[#1e1e1e] border border-white/10 rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">
                        <div className="p-4 border-b border-white/10 flex justify-between items-center">
                            <h3 className="font-bold flex items-center gap-2"><Sparkles size={16} className="text-amber-300"/> {t('确认补充实体提示词', 'Confirm Entity Supplement Prompt')}</h3>
                            <button onClick={() => setSceneRegenPromptModal({ open: false, loading: false, data: null })}><X size={18}/></button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-4 space-y-4">
                            {sceneRegenPromptModal.loading && !sceneRegenPromptModal.data ? (
                                <div className="flex items-center justify-center h-40"><Loader2 className="animate-spin text-amber-300" size={32}/></div>
                            ) : (
                                <>
                                    <div className="bg-amber-500/10 border border-amber-500/20 rounded p-3 text-xs text-amber-100 flex items-start gap-2">
                                        <Info size={14} className="shrink-0 mt-0.5" />
                                        {t('超级用户模式：请确认提示词后再提交重生成。', 'Superuser mode: confirm prompt before submitting regeneration.')}
                                    </div>

                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-bold text-muted-foreground uppercase">{t('用户提示词预览（只读）', 'User Prompt Preview (Read-only)')}</label>
                                        <textarea
                                            readOnly
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-xs text-white/80 font-mono h-56 focus:outline-none resize-y"
                                            value={sceneRegenPromptModal.data?.user_prompt_preview || ''}
                                        />
                                    </div>

                                    <div className="flex flex-col gap-2">
                                        <label className="text-xs font-bold text-muted-foreground uppercase">{t('系统提示词（可编辑）', 'System Prompt (Editable)')}</label>
                                        <textarea
                                            className="bg-black/30 border border-white/10 rounded-md p-3 text-xs text-muted-foreground font-mono h-48 focus:outline-none focus:border-amber-400/50 resize-y"
                                            value={sceneRegenPromptModal.data?.system_prompt || ''}
                                            onChange={e => setSceneRegenPromptModal(prev => ({
                                                ...prev,
                                                data: { ...(prev.data || {}), system_prompt: e.target.value },
                                            }))}
                                        />
                                    </div>
                                </>
                            )}
                        </div>

                        <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                            <button
                                onClick={() => {
                                    const full = String(sceneRegenPromptModal.data?.system_prompt || '');
                                    navigator.clipboard.writeText(full);
                                    onLog?.(t('系统提示词已复制到剪贴板', 'System prompt copied to clipboard'), 'success');
                                }}
                                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded text-sm font-medium flex items-center gap-2 mr-auto"
                            >
                                <Copy size={16}/> {t('复制系统提示词', 'Copy System Prompt')}
                            </button>
                            <button
                                onClick={() => setSceneRegenPromptModal({ open: false, loading: false, data: null })}
                                className="px-4 py-2 rounded hover:bg-white/10 text-sm"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button
                                onClick={async () => {
                                    setSceneRegenPromptModal(prev => ({ ...prev, loading: true }));
                                    try {
                                        await handleRegenerateScene({
                                            system_prompt: sceneRegenPromptModal.data?.system_prompt || '',
                                        });
                                        setSceneRegenPromptModal({ open: false, loading: false, data: null });
                                    } catch {
                                        setSceneRegenPromptModal(prev => ({ ...prev, loading: false }));
                                    }
                                }}
                                disabled={sceneRegenPromptModal.loading}
                                className="px-6 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded text-sm font-medium flex items-center gap-2"
                            >
                                {sceneRegenPromptModal.loading ? <Loader2 className="animate-spin" size={16}/> : <Sparkles size={16}/>}
                                {sceneRegenPromptModal.loading ? t('提交中...', 'Submitting...') : t('确认并重生成', 'Confirm & Regenerate')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {aiShotRowEditor.open && (
                <div className="fixed inset-0 z-[60] bg-black/85 flex items-center justify-center p-4" onClick={() => setAiShotRowEditor({ open: false, index: -1, data: null })}>
                    <div className="bg-[#1b1b1b] border border-white/10 rounded-xl w-full max-w-3xl max-h-[88vh] overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
                        <div className="p-4 border-b border-white/10 flex items-center justify-between">
                            <h3 className="font-bold text-white">{t('编辑 AI 镜头行', 'Edit AI Shot Row')} #{aiShotRowEditor.index + 1}</h3>
                            <button onClick={() => setAiShotRowEditor({ open: false, index: -1, data: null })} className="p-1 hover:bg-white/10 rounded"><X size={18}/></button>
                        </div>
                        <div className="p-4 space-y-3 overflow-y-auto custom-scrollbar max-h-[68vh]">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <InputGroup label={t('镜头 ID', 'Shot ID')} value={aiShotRowEditor.data?.shot_id || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), shot_id: v } }))} />
                                <InputGroup label={t('镜头名称', 'Shot Name')} value={aiShotRowEditor.data?.shot_name || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), shot_name: v } }))} />
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <InputGroup label={t('场景 ID', 'Scene ID')} value={aiShotRowEditor.data?.scene_id || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), scene_id: v } }))} />
                                <InputGroup label={t('时长（秒）', 'Duration (s)')} value={aiShotRowEditor.data?.duration || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), duration: v } }))} />
                            </div>
                            <InputGroup label={t('镜头逻辑（中文）', 'Shot Logic (CN)')} value={aiShotRowEditor.data?.shot_logic_cn || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), shot_logic_cn: v } }))} />
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <InputGroup label={t('起始帧（中文）', 'Start Frame (CN)')} value={aiShotRowEditor.data?.start_frame_cn || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), start_frame_cn: v } }))} />
                                <InputGroup label={t('视频内容（中文）', 'Video Content (CN)')} value={aiShotRowEditor.data?.video_content_cn || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), video_content_cn: v } }))} />
                                <InputGroup label={t('关键帧（中文）', 'Keyframes (CN)')} value={aiShotRowEditor.data?.keyframes_cn || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), keyframes_cn: v } }))} />
                                <InputGroup label={t('收尾帧（中文）', 'End Frame (CN)')} value={aiShotRowEditor.data?.end_frame_cn || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), end_frame_cn: v } }))} />
                            </div>
                            <InputGroup label={t('关联实体', 'Associated Entities')} value={aiShotRowEditor.data?.associated_entities || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), associated_entities: v } }))} />
                            <InputGroup label={t('关键帧', 'Keyframes')} value={aiShotRowEditor.data?.keyframes || ''} onChange={v => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), keyframes: v } }))} />
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-1 block">{t('起始帧', 'Start Frame')}</label>
                                <textarea
                                    className="w-full bg-black/40 border border-white/10 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-y custom-scrollbar font-mono leading-relaxed min-h-[120px]"
                                    value={aiShotRowEditor.data?.start_frame || ''}
                                    onChange={e => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), start_frame: e.target.value } }))}
                                />
                            </div>
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-1 block">{t('视频内容', 'Video Content')}</label>
                                <textarea
                                    className="w-full bg-black/40 border border-white/10 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-y custom-scrollbar font-mono leading-relaxed min-h-[180px]"
                                    value={aiShotRowEditor.data?.video_content || ''}
                                    onChange={e => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), video_content: e.target.value } }))}
                                />
                            </div>
                            <div>
                                <label className="text-xs text-muted-foreground uppercase font-bold tracking-wider mb-1 block">{t('结束帧', 'End Frame')}</label>
                                <textarea
                                    className="w-full bg-black/40 border border-white/10 rounded p-3 text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary resize-y custom-scrollbar font-mono leading-relaxed min-h-[120px]"
                                    value={aiShotRowEditor.data?.end_frame || ''}
                                    onChange={e => setAiShotRowEditor(prev => ({ ...prev, data: { ...(prev.data || {}), end_frame: e.target.value } }))}
                                />
                            </div>
                        </div>
                        <div className="p-4 border-t border-white/10 flex justify-end gap-2 bg-black/20">
                            <button onClick={() => setAiShotRowEditor({ open: false, index: -1, data: null })} className="px-4 py-2 rounded hover:bg-white/10 text-sm">{t('取消', 'Cancel')}</button>
                            <button onClick={saveAiShotRowEditor} className="px-5 py-2 bg-primary text-black rounded font-bold text-sm hover:bg-primary/90">{t('保存行', 'Save Row')}</button>
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
};

