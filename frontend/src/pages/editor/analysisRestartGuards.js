export const THIS_RUN_PIPELINE_NODE_SLACK_MS = 2000;

function parsePipelineNodeTime(node) {
    const raw = node?.started_at || node?.updated_at || node?.ended_at || '';
    if (typeof raw === 'number' && Number.isFinite(raw) && raw > 0) return raw;
    const text = String(raw || '').trim();
    if (!text) return 0;
    const normalized = text.includes('T') ? text : text.replace(' ', 'T');
    const ts = Date.parse(normalized);
    if (Number.isFinite(ts)) return ts;
    const noMicro = normalized.replace(/(\.\d{3})\d+/, '$1');
    const ts2 = Date.parse(noMicro);
    return Number.isFinite(ts2) ? ts2 : 0;
}

/** True when a pipeline node was written during the current analysis clock. */
export function isThisRunPipelineNode(node, runStartedAt, slackMs = THIS_RUN_PIPELINE_NODE_SLACK_MS) {
    const runAt = Number(runStartedAt || 0);
    if (runAt <= 0) return false;
    const ts = parsePipelineNodeTime(node);
    if (!ts) return false;
    return ts >= (runAt - Number(slackMs || 0));
}

/**
 * Full restart must ignore last-run staging success until this-run scenes exist.
 * Do not use trustLiveDownstreamOnly here — that flag stays true for the whole
 * analysis and would block this-run 建置 after 美术指导 finishes.
 */
export function shouldRejectLeftoverStagingKickoff({
    fullRestartGate = false,
    node = null,
    runStartedAt = 0,
    inThisRunAllowlist = false,
} = {}) {
    if (!fullRestartGate) return false;
    if (inThisRunAllowlist) return false;
    const runAt = Number(runStartedAt || 0);
    // No run clock: cannot prove leftover, so do not block this-run 建置.
    if (runAt <= 0) return false;
    if (isThisRunPipelineNode(node, runStartedAt)) return false;
    return true;
}

function pipelineNodeInstant(node, fields) {
    for (const field of fields) {
        const ts = parsePipelineNodeTime({ [field]: node?.[field] });
        if (ts) return ts;
    }
    return 0;
}

/**
 * A rerun queues storyboard_generation before 文戏 finishes. That queued row is a
 * placeholder. Kick off shots only after this run's 建置 success is newer than the queue.
 * Leftover staging success from the previous run must not open generateSceneShots.
 */
export function shouldHoldStoryboardKickoffForQueuedPlaceholder(stagingNode, storyboardNode) {
    const status = String(storyboardNode?.status || '').trim().toLowerCase();
    const event = String(storyboardNode?.runtime_meta?.business_event || '').trim().toLowerCase();
    const placeholder = status === 'queued'
        || event === 'queued'
        || Boolean(storyboardNode?.runtime_meta?.rerun_cleared);
    if (!placeholder) return false;
    const queuedAt = pipelineNodeInstant(storyboardNode, ['updated_at', 'started_at']);
    const stagingDoneAt = pipelineNodeInstant(stagingNode, ['ended_at', 'updated_at']);
    if (!queuedAt || !stagingDoneAt) return true;
    return stagingDoneAt <= queuedAt;
}

export function isSuccessfulPipelineNode(node, names = []) {
    const name = String(node?.node_name || '').trim();
    if (names.length && !names.includes(name)) return false;
    return ['success', 'warning'].includes(String(node?.status || '').trim().toLowerCase());
}

export function hasSuccessfulPipelineNode(nodes, name) {
    const wanted = String(name || '').trim();
    if (!wanted) return false;
    return (Array.isArray(nodes) ? nodes : []).some((node) => isSuccessfulPipelineNode(node, [wanted]));
}
