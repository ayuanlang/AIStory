import { parseShotsFromMarkdownTable, stripShotLogicPrefixFromVideoPrompt } from './sceneTableParser';

export const getStagingShotField = (shot, field) => {
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

const BR_SPLIT_PATTERN = new RegExp('\\n|<br\\s*/?>', 'i');
const BR_JOIN = '<br>';

export const splitCombinedCnPrompt = (raw) => {
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
        .split(BR_SPLIT_PATTERN)
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

export const extractShotRegenMarker = (rawLogic) => {
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

export const buildShotWritePayloadFromRow = (shot, options = {}) => {
    const fallbackSceneCode = String(options?.fallbackSceneCode || '').trim();
    const existingTechnicalNotes = String(options?.existingTechnicalNotes || '').trim();
    const promptCnRaw = String(shot?.['Prompt (CN)'] || shot?.prompt_cn || '').trim();
    const startFrameCnRaw = getStagingShotField(shot, 'start_frame_cn');
    const videoPromptCnRaw = stripShotLogicPrefixFromVideoPrompt(getStagingShotField(shot, 'video_content_cn'))
        || stripShotLogicPrefixFromVideoPrompt(getStagingShotField(shot, 'shot_logic_cn'));
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
        ].join(BR_JOIN);
    }

    const rawLogic = getStagingShotField(shot, 'shot_logic_cn');
    const { cleanLogic } = extractShotRegenMarker(rawLogic);

    return {
        shot_id: getStagingShotField(shot, 'shot_id'),
        shot_name: getStagingShotField(shot, 'shot_name'),
        scene_code: getStagingShotField(shot, 'scene_id') || fallbackSceneCode,
        start_frame: getStagingShotField(shot, 'start_frame'),
        end_frame: getStagingShotField(shot, 'end_frame'),
        video_content: getStagingShotField(shot, 'video_content'),
        duration: getStagingShotField(shot, 'duration'),
        associated_entities: getStagingShotField(shot, 'associated_entities'),
        shot_logic_cn: cleanLogic || rawLogic,
        keyframes: getStagingShotField(shot, 'keyframes'),
        technical_notes: Object.keys(technicalNotesObj).length > 0 ? JSON.stringify(technicalNotesObj) : existingTechnicalNotes || '',
    };
};

export const resolveAiShotsStagingRows = (rawText, serverContent = [], warnings = []) => {
    const content = Array.isArray(serverContent) ? serverContent : [];
    const markdown = String(rawText || '').trim();
    if (!markdown) {
        return { content, warnings: Array.isArray(warnings) ? [...warnings] : [] };
    }

    const reparsed = parseShotsFromMarkdownTable(markdown);
    const reparsedRows = Array.isArray(reparsed?.rows) ? reparsed.rows : [];
    const nextWarnings = Array.isArray(warnings) ? [...warnings] : [];

    if (reparsedRows.length > content.length) {
        nextWarnings.push(
            `Reparsed ${reparsedRows.length} shots from stored markdown (staging table had ${content.length}).`
        );
        return { content: reparsedRows, warnings: nextWarnings };
    }

    return { content, warnings: nextWarnings };
};

export const findStagingRowByShotId = (rows, shotId) => {
    const normalizedTarget = String(shotId || '').trim().toUpperCase();
    if (!normalizedTarget) return null;
    const list = Array.isArray(rows) ? rows : [];
    return list.find((row) => String(getStagingShotField(row, 'shot_id') || '').trim().toUpperCase() === normalizedTarget) || null;
};