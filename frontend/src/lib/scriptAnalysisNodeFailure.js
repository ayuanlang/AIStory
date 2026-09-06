/** Classify a failed script-analysis pipeline node for inspect UI + AI diagnosis. */

const clip = (value, max = 800) => {
    const text = String(value || '').trim();
    if (!text) return '';
    if (text.length <= max) return text;
    return `${text.slice(0, max)}…`;
};

const joinReasonParts = (...parts) => (
    parts.map((part) => String(part || '').trim()).filter(Boolean)
);

export const isFailedPipelineStatus = (status) => (
    ['failed', 'blocked', 'error', 'timeout'].includes(String(status || '').trim().toLowerCase())
);

export const collectNodeFailureSource = (node = null, extra = {}) => {
    const meta = node?.runtime_meta && typeof node.runtime_meta === 'object' ? node.runtime_meta : {};
    return {
        errorCode: String(extra.errorCode || node?.last_error_code || '').trim(),
        errorMessage: String(extra.errorMessage || node?.last_error_message || extra.detail || '').trim(),
        businessReason: String(extra.businessReason || meta.business_reason || '').trim(),
        detail: String(extra.detail || meta.current_step_label || '').trim(),
        currentStep: String(extra.currentStep || meta.current_step || '').trim(),
        status: String(extra.status || node?.status || '').trim().toLowerCase(),
    };
};

const classifyFailureKind = ({ errorCode, errorMessage, businessReason, detail, status }) => {
    const code = String(errorCode || '').trim().toUpperCase();
    const raw = `${errorMessage}\n${businessReason}\n${detail}`.trim();
    const lower = raw.toLowerCase();

    if (
        code === 'INSUFFICIENT_CREDITS'
        || /insufficient[_\s-]?credits/i.test(raw)
        || raw.includes('积分不足')
        || raw.includes('个人积分不足')
        || raw.includes('组积分不足')
        || (raw.includes('余额不足') && !raw.includes('供应商'))
    ) {
        return 'credits_user';
    }
    if (
        code === 'VENDOR_BALANCE_INSUFFICIENT'
        || raw.includes('供应商侧余额不足')
        || raw.includes('供应商余额不足')
        || raw.includes('无权调用该模型')
    ) {
        return 'credits_vendor';
    }
    if (
        code === 'NODE_TIMEOUT'
        || code === 'SCENE_SUBSKILL_TIMEOUT'
        || /超过\s*\d+s\s*无进展/.test(raw)
        || /timed out after \d+s with no progress/i.test(raw)
        || lower.includes('timeout')
    ) {
        return 'timeout';
    }
    if (code === 'PROMPT_INJECTION_DETECTED' || raw.includes('PROMPT_INJECTION')) {
        return 'prompt_injection';
    }
    if (code === 'PROMPT_LEAK_DETECTED' || raw.includes('PROMPT_LEAK')) {
        return 'prompt_leak';
    }
    if (code === 'COMPLETION_MARKER_MISSING' || raw.includes('COMPLETION_MARKER_MISSING')) {
        return 'incomplete_output';
    }
    if (code === 'OUTPUT_PARSE_FAILED' || raw.includes('OUTPUT_PARSE_FAILED')) {
        return 'parse_failed';
    }
    if (code === 'OUTPUT_SCENE_MISMATCH' || raw.includes('OUTPUT_SCENE_MISMATCH')) {
        return 'scene_mismatch';
    }
    if (code === 'SCENE_SUBSKILL_CANCELLED' || /canceled|cancelled|已取消/.test(lower)) {
        return 'cancelled';
    }
    const looksLikeEnvWait = /waiting_env|wait_env|等待环境/.test(lower)
        || (/主环境/.test(raw) && /未/.test(raw));
    if (code === 'STORYBOARD_GENERATION_FAILED') {
        return looksLikeEnvWait ? 'storyboard_env' : 'storyboard_generation';
    }
    if (code === 'STORYBOARD_JOB_FAILED' || looksLikeEnvWait) {
        return looksLikeEnvWait ? 'storyboard_env' : 'storyboard_generation';
    }
    if (
        code === 'SCENE_IMPORT_FAILED'
        || /workspace_import_failed|import_no_result/.test(lower)
        || raw.includes('场景未写入工作区')
    ) {
        return 'import_failed';
    }
    if (code === 'ASSETS_EXTRACTION_COVER_POSTER_MISSING') {
        return 'cover_missing';
    }
    if (code === 'SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING') {
        return 'visual_backfill_missing';
    }
    if (status === 'blocked') {
        return 'blocked';
    }
    if (code || raw) {
        return 'generic';
    }
    return 'unknown';
};

export const explainScriptAnalysisNodeFailure = (source, tFn) => {
    const t = typeof tFn === 'function' ? tFn : (zh) => zh;
    const input = collectNodeFailureSource(null, source);
    const kind = classifyFailureKind(input);
    const rawError = clip(joinReasonParts(input.businessReason, input.errorMessage, input.detail)[0] || '');
    const errorCode = input.errorCode;

    const reasonByKind = {
        credits_user: t('积分不足，本次节点没有跑完。', 'Credits ran out, so this node did not finish.'),
        credits_vendor: t('当前分析接口的供应商余额不足，或无权调用该模型。', 'The current analysis API has insufficient vendor balance, or this model is not authorized.'),
        timeout: t('该节点超时，长时间没有新进展。', 'This node timed out with no further progress.'),
        prompt_injection: t('内容被识别为提示词注入，已拦截。', 'The content was flagged as prompt injection and blocked.'),
        prompt_leak: t('内容被识别为提示词泄漏，已拦截。', 'The content was flagged as a prompt leak and blocked.'),
        incomplete_output: t('模型返回不完整，结束标记缺失，自动重试后仍未完整。', 'The model returned incomplete output (missing end marker) even after automatic retry.'),
        parse_failed: t('返回的结构无法解析，不能作为本节点成稿。', 'The returned structure could not be parsed, so this node has no usable draft.'),
        scene_mismatch: t('返回的场号与当前场次不一致。', 'The returned scene ID does not match this scene.'),
        cancelled: t('该节点已被取消或中途停止。', 'This node was canceled or stopped mid-run.'),
        storyboard_generation: rawError || t('分镜生成失败。', 'Storyboard generation failed.'),
        storyboard_env: t('分镜未完成，通常是场景未入库或本场主环境未齐套。', 'Storyboard did not finish, usually because the scene is not imported or its main environment is not ready.'),
        import_failed: t('建置稿没有写入工作区场景表。', 'The staging draft was not written into the workspace scene table.'),
        cover_missing: t('封面海报简报缺失，环境设计无法收口。', 'The cover-poster brief is missing, so environment design cannot finish.'),
        visual_backfill_missing: t('项目视觉回填缺失，全局统筹没有形成完整成稿。', 'Project visual backfill is missing, so global orchestration has no complete draft.'),
        blocked: t('该节点被上游或依赖拦住，还不能继续。', 'This node is blocked by an upstream step or a missing dependency.'),
        generic: rawError || t('该节点已标记失败。', 'This node is marked failed.'),
        unknown: t('该节点已标记失败，但没有留下详细错误。', 'This node is marked failed, but no detailed error was stored.'),
    };

    const suggestionsByKind = {
        credits_user: [
            t('先充值，再只重跑这个失败节点，不必整集重开。', 'Top up credits, then rerun only this failed node.'),
            t('若组积分不足，联系组管理员分配额度。', 'If group credits are low, ask a group admin to allocate more.'),
        ],
        credits_vendor: [
            t('在本页把「剧本分析 API」换成其他可用接口后再重跑该节点。', 'Switch the script-analysis API on this page, then rerun this node.'),
            t('若只有这一家接口，联系管理员检查供应商余额与模型授权。', 'If this is the only API, ask an admin to check vendor balance and model access.'),
        ],
        timeout: [
            t('直接重跑该节点；网络抖动时多数一次就能过。', 'Rerun this node; a transient timeout often succeeds on retry.'),
            t('若反复超时，把剧本分析 API 换成更稳的模型（优先 G1 Gemini 2.5）。', 'If it keeps timing out, switch to a more stable model (prefer G1 Gemini 2.5).'),
            t('单场失败只重跑该场，不要整集重开。', 'If only one scene failed, rerun that scene only.'),
        ],
        prompt_injection: [
            t('检查本集剧本或该场草稿是否误贴了提示词、系统指令或代码块。', 'Check the episode script or this scene draft for pasted prompts, system instructions, or code blocks.'),
            t('删掉可疑段落后再重跑该节点。', 'Remove the suspicious text, then rerun this node.'),
        ],
        prompt_leak: [
            t('检查是否把内部提示词或系统说明写进了剧本。', 'Check whether internal prompts or system notes were pasted into the script.'),
            t('改回正常剧情叙述后再重跑。', 'Restore normal story wording, then rerun.'),
        ],
        incomplete_output: [
            t('重跑该节点；不完整返回常由模型截断引起。', 'Rerun this node; incomplete returns are often model truncation.'),
            t('若连续不完整，换 G1 Gemini 2.5 或 DeepSeek 后再重跑。', 'If it stays incomplete, switch to G1 Gemini 2.5 or DeepSeek and rerun.'),
        ],
        parse_failed: [
            t('先打开该节点「编辑」看草稿是否残缺，再重跑。', 'Open Edit on this node to see if the draft is truncated, then rerun.'),
            t('上游刚改过时，先确认上游成稿完整，再重跑本节点。', 'If an upstream step just changed, confirm that draft is complete before rerunning this node.'),
        ],
        scene_mismatch: [
            t('重跑该场节点；场号被模型写错时重跑通常能对齐。', 'Rerun this scene node; a wrong scene ID is often fixed on retry.'),
            t('若场号整体乱了，回到全局统筹检查切场结果后再往下跑。', 'If scene IDs are broadly wrong, check global orchestration first.'),
        ],
        cancelled: [
            t('用「继续分析」或该节点「重跑」接着做，不必整集重开。', 'Use Continue analysis or Rerun on this node; do not restart the whole episode.'),
        ],
        storyboard_generation: [
            t('只重跑该场分镜；超时或模型抖动时多数一次就能过。', 'Rerun this scene’s storyboard; a timeout or model flake often succeeds on retry.'),
            t('反复失败时换一个剧本分析 API，或开 AI 诊断对照原始错误判断。', 'If it keeps failing, switch the script-analysis API or open AI Diagnosis with the raw error.'),
        ],
        storyboard_env: [
            t('先确认该场建置已入库，且本场主环境已生成。', 'Confirm this scene is imported and its main environment is generated.'),
            t('环境未齐套时先重跑「环境生成」，再重跑该场分镜。', 'If the environment is missing, rerun Environment Gen, then this scene’s storyboard.'),
        ],
        import_failed: [
            t('打开该场建置入戏，确认有完整建置稿后再点重跑。', 'Open this scene’s staging node, confirm the draft is complete, then rerun.'),
            t('场号或场景名缺失时，先改草稿再导入。', 'If the scene number or name is missing, fix the draft before importing.'),
        ],
        cover_missing: [
            t('先重跑环境规划，确认封面海报简报在，再重跑环境生成。', 'Rerun environment planning so the cover brief exists, then rerun environment generation.'),
        ],
        visual_backfill_missing: [
            t('重跑全局统筹，让项目视觉回填写完整。', 'Rerun global orchestration so project visual backfill is complete.'),
        ],
        blocked: [
            t('先看左侧/上游节点是否仍在处理或已失败，先恢复上游。', 'Check the upstream node first; unblock or rerun that step.'),
            t('上游完成后，再重跑本节点。', 'After the upstream step succeeds, rerun this node.'),
        ],
        generic: [
            t('只重跑这个失败节点，不要整集重开。', 'Rerun only this failed node; do not restart the whole episode.'),
            t('反复失败时换一个剧本分析 API，或开 AI 诊断让助手对照手册判断。', 'If it keeps failing, switch the script-analysis API or open AI Diagnosis.'),
        ],
        unknown: [
            t('先点「重跑」再试一次。', 'Try Rerun once.'),
            t('仍失败就开 AI 诊断，把节点和日志交给助手判断。', 'If it fails again, open AI Diagnosis with this node and the logs.'),
        ],
    };

    const reason = reasonByKind[kind] || reasonByKind.unknown;
    const suggestions = suggestionsByKind[kind] || suggestionsByKind.unknown;
    return {
        kind,
        errorCode,
        reason,
        rawError,
        suggestions,
    };
};

export const buildFailedNodeDiagnosisSummary = ({
    label = '',
    sceneId = '',
    sceneLabel = '',
    errorCode = '',
    reason = '',
    rawError = '',
    suggestions = [],
} = {}) => {
    const lines = [
        '当前关注失败节点：',
        `- 节点：${label || '未知'}`,
        `- 场次：${sceneLabel || sceneId || '全局'}`,
        errorCode ? `- 错误码：${errorCode}` : '',
        reason ? `- 错误原因：${reason}` : '',
        rawError && rawError !== reason ? `- 原始错误：${clip(rawError, 1200)}` : '',
        suggestions.length ? `- 处理建议：${suggestions.join('；')}` : '',
    ].filter(Boolean);
    return lines.join('\n');
};

export const buildFailedNodeDiagnosisQuery = ({ label = '', sceneId = '', reason = '' } = {}, tFn) => {
    const t = typeof tFn === 'function' ? tFn : (zh) => zh;
    const nodeName = label || t('该节点', 'this node');
    const scenePart = sceneId
        ? t(`（场次 ${sceneId}）`, ` (scene ${sceneId})`)
        : '';
    const reasonText = String(reason || '').trim().replace(/[。.\s]+$/, '');
    const reasonPart = reasonText
        ? t(`错误原因：${reasonText}。`, `Failure reason: ${reasonText}. `)
        : '';
    return t(
        `节点「${nodeName}」${scenePart}失败了。${reasonPart}请针对这个节点诊断：现在卡在哪里、为什么失败、下一步该怎么处理（优先局部重跑/换接口/补上游，不要建议整集重开）。`,
        `Node "${nodeName}"${scenePart} failed. ${reasonPart}Diagnose this node: where it is stuck, why it failed, and what to do next (prefer local rerun / switch API / fix upstream; do not restart the whole episode).`
    );
};
