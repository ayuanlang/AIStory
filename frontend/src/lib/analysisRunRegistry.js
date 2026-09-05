const analysisRunsByEpisode = new Map();
/** Soft-start / in-flight claims that survive ScriptEditor remount (episode refresh). */
const analysisClaimsByEpisode = new Map();
/** Live progress UI snapshots that survive ScriptEditor remount. */
const analysisProgressByEpisode = new Map();
const analysisProgressListenersByEpisode = new Map();
/** Episodes whose ScriptEditor unmounted while a run promise is still live. */
const detachedAnalysisEpisodes = new Set();
/**
 * Pipeline control plane that survives ScriptEditor remount.
 * Stop/timeout must be readable by the original run closure after the user leaves and returns.
 */
const analysisPipelineControlByEpisode = new Map();

function toEpisodeId(episodeId) {
    return Number(episodeId || 0);
}

function emptyPipelineControl() {
    return {
        stopRequested: false,
        stopReason: '', // 'user' | 'timeout' | ''
        deadlineAt: 0,
        supervisorActive: false,
        startedAt: 0,
        updatedAt: 0,
    };
}

export function getEpisodeAnalysisPipelineControl(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return emptyPipelineControl();
    return analysisPipelineControlByEpisode.get(id) || emptyPipelineControl();
}

export function armEpisodeAnalysisPipelineControl(episodeId, {
    startedAt = Date.now(),
    maxMs = 60 * 60 * 1000,
} = {}) {
    const id = toEpisodeId(episodeId);
    if (!id) return null;
    const start = Number(startedAt || Date.now());
    const budget = Math.max(60 * 1000, Number(maxMs || 0) || (60 * 60 * 1000));
    const next = {
        stopRequested: false,
        stopReason: '',
        deadlineAt: (Number.isFinite(start) && start > 0 ? start : Date.now()) + budget,
        supervisorActive: true,
        startedAt: Number.isFinite(start) && start > 0 ? start : Date.now(),
        updatedAt: Date.now(),
    };
    analysisPipelineControlByEpisode.set(id, next);
    return next;
}

export function requestEpisodeAnalysisPipelineStop(episodeId, reason = 'user') {
    const id = toEpisodeId(episodeId);
    if (!id) return null;
    const prev = analysisPipelineControlByEpisode.get(id) || emptyPipelineControl();
    const next = {
        ...prev,
        stopRequested: true,
        stopReason: String(reason || 'user').trim() || 'user',
        updatedAt: Date.now(),
    };
    analysisPipelineControlByEpisode.set(id, next);
    return next;
}

export function clearEpisodeAnalysisPipelineControl(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return;
    analysisPipelineControlByEpisode.delete(id);
}

export function getEpisodeAnalysisPipelineRemainingMs(episodeId) {
    const control = getEpisodeAnalysisPipelineControl(episodeId);
    const deadline = Number(control.deadlineAt || 0);
    if (!Number.isFinite(deadline) || deadline <= 0) return Number.POSITIVE_INFINITY;
    return Math.max(0, deadline - Date.now());
}

function emptyProgressSnapshot() {
    return {
        flowStatus: { phase: 'idle', message: '' },
        flowHistory: [],
        detailLogs: [],
        uiReport: null,
        isAnalyzing: false,
        pipelineNodes: [],
        sceneUnits: [],
        updatedAt: 0,
    };
}

export function hasInFlightPipelineNodes(nodes) {
    return (Array.isArray(nodes) ? nodes : []).some((node) => {
        const status = String(node?.status || '').trim().toLowerCase();
        if (!['running', 'queued'].includes(status)) return false;
        const name = String(node?.node_name || '').trim();
        // Frontend owns per-scene generateSceneShots. A leftover queued/running
        // storyboard_generation placeholder must not keep the analysis UI live.
        if (
            (status === 'queued' || status === 'running')
            && (name === 'storyboard_generation' || name === 'shot_generation')
        ) {
            return false;
        }
        return true;
    });
}

export function trackEpisodeAnalysisRun(episodeId, runPromise, meta = {}) {
    const id = toEpisodeId(episodeId);
    if (!id || !runPromise) return null;

    const entry = {
        episodeId: id,
        promise: runPromise,
        startedAt: Number(meta.startedAt || Date.now()),
        kind: String(meta.kind || 'analysis'),
        phase: meta.phase ?? 1,
        taskId: String(meta.taskId || '').trim(),
        claimToken: String(meta.claimToken || analysisClaimsByEpisode.get(id)?.token || '').trim(),
    };
    analysisRunsByEpisode.set(id, entry);

    // Ensure a claim stays alive for the whole tracked run (covers remount mid-flight).
    if (entry.claimToken) {
        analysisClaimsByEpisode.set(id, {
            token: entry.claimToken,
            claimedAt: Number(meta.startedAt || Date.now()),
            source: String(meta.kind || 'analysis'),
        });
    } else {
        const token = `run_${id}_${Date.now()}`;
        entry.claimToken = token;
        analysisClaimsByEpisode.set(id, {
            token,
            claimedAt: Number(meta.startedAt || Date.now()),
            source: String(meta.kind || 'analysis'),
        });
    }

    runPromise.finally(() => {
        const current = analysisRunsByEpisode.get(id);
        if (current?.promise === runPromise) {
            analysisRunsByEpisode.delete(id);
            releaseEpisodeAnalysisClaim(id, entry.claimToken);
            clearEpisodeAnalysisDetached(id);
            clearEpisodeAnalysisPipelineControl(id);
            return;
        }
        // Abandoned by user stop / a newer run already replaced this entry.
        // Never wipe the new run's claim or pipeline control.
        releaseEpisodeAnalysisClaim(id, entry.claimToken);
    });

    return entry;
}

export function getEpisodeAnalysisRun(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return null;
    return analysisRunsByEpisode.get(id) || null;
}

export function updateEpisodeAnalysisRun(episodeId, patch = {}) {
    const entry = getEpisodeAnalysisRun(episodeId);
    if (!entry) return null;
    Object.assign(entry, patch);
    return entry;
}

export function releaseEpisodeAnalysisRun(episodeId, runPromise = null) {
    const id = toEpisodeId(episodeId);
    if (!id) return;
    const current = analysisRunsByEpisode.get(id);
    if (!current) return;
    if (runPromise && current.promise !== runPromise) return;
    analysisRunsByEpisode.delete(id);
    clearEpisodeAnalysisDetached(id);
}

/**
 * Try to claim an episode analysis start. Fails if another start/run already holds the claim.
 * Survives component remount (module-level).
 */
export function tryClaimEpisodeAnalysis(episodeId, source = 'analysis') {
    const id = toEpisodeId(episodeId);
    if (!id) return { ok: false, token: '', reason: 'no_episode' };
    if (analysisClaimsByEpisode.has(id) || analysisRunsByEpisode.has(id)) {
        return { ok: false, token: '', reason: 'busy' };
    }
    const token = `claim_${id}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    analysisClaimsByEpisode.set(id, {
        token,
        claimedAt: Date.now(),
        source: String(source || 'analysis'),
    });
    return { ok: true, token, reason: '' };
}

/**
 * Take over / refresh claim for an intentional regenerate after user confirmation.
 */
export function forceClaimEpisodeAnalysis(episodeId, source = 'analysis') {
    const id = toEpisodeId(episodeId);
    if (!id) return { ok: false, token: '', reason: 'no_episode' };
    const token = `claim_${id}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    analysisClaimsByEpisode.set(id, {
        token,
        claimedAt: Date.now(),
        source: String(source || 'analysis'),
    });
    return { ok: true, token, reason: '' };
}

export function releaseEpisodeAnalysisClaim(episodeId, token = null) {
    const id = toEpisodeId(episodeId);
    if (!id) return false;
    const current = analysisClaimsByEpisode.get(id);
    if (!current) return false;
    if (token && current.token !== token) return false;
    analysisClaimsByEpisode.delete(id);
    return true;
}

export function isEpisodeAnalysisClaimed(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return false;
    return analysisClaimsByEpisode.has(id) || analysisRunsByEpisode.has(id);
}

export function getEpisodeAnalysisClaim(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return null;
    return analysisClaimsByEpisode.get(id) || null;
}

export function markEpisodeAnalysisDetached(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return;
    detachedAnalysisEpisodes.add(id);
}

export function clearEpisodeAnalysisDetached(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return;
    detachedAnalysisEpisodes.delete(id);
}

export function isEpisodeAnalysisDetached(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return false;
    return detachedAnalysisEpisodes.has(id);
}

/**
 * Publish live progress for an episode. Survives ScriptEditor unmount so remount can subscribe.
 * Patch fields merge shallowly; arrays/objects in the patch replace that field.
 */
export function publishEpisodeAnalysisProgress(episodeId, patch = {}) {
    const id = toEpisodeId(episodeId);
    if (!id || !patch || typeof patch !== 'object') return null;

    const prev = analysisProgressByEpisode.get(id) || emptyProgressSnapshot();
    const next = {
        ...prev,
        ...patch,
        updatedAt: Date.now(),
    };
    if (patch.flowStatus && typeof patch.flowStatus === 'object') {
        next.flowStatus = { ...(prev.flowStatus || {}), ...patch.flowStatus };
    }
    if (Object.prototype.hasOwnProperty.call(patch, 'uiReport')) {
        next.uiReport = patch.uiReport && typeof patch.uiReport === 'object'
            ? { ...(prev.uiReport || {}), ...patch.uiReport }
            : patch.uiReport;
    }
    if (Object.prototype.hasOwnProperty.call(patch, 'flowHistory') && Array.isArray(patch.flowHistory)) {
        next.flowHistory = patch.flowHistory;
    }
    if (Object.prototype.hasOwnProperty.call(patch, 'detailLogs') && Array.isArray(patch.detailLogs)) {
        next.detailLogs = patch.detailLogs;
    }
    if (Object.prototype.hasOwnProperty.call(patch, 'isAnalyzing')) {
        next.isAnalyzing = Boolean(patch.isAnalyzing);
    }
    if (Object.prototype.hasOwnProperty.call(patch, 'pipelineNodes') && Array.isArray(patch.pipelineNodes)) {
        next.pipelineNodes = patch.pipelineNodes;
    }
    if (Object.prototype.hasOwnProperty.call(patch, 'sceneUnits') && Array.isArray(patch.sceneUnits)) {
        next.sceneUnits = patch.sceneUnits;
    }
    analysisProgressByEpisode.set(id, next);

    const listeners = analysisProgressListenersByEpisode.get(id);
    if (listeners && listeners.size > 0) {
        listeners.forEach((listener) => {
            try {
                listener(next);
            } catch (_) {
                // Ignore subscriber failures so publishers keep running.
            }
        });
    }
    return next;
}

export function getEpisodeAnalysisProgress(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return null;
    return analysisProgressByEpisode.get(id) || null;
}

export function clearEpisodeAnalysisProgress(episodeId) {
    const id = toEpisodeId(episodeId);
    if (!id) return;
    analysisProgressByEpisode.delete(id);
}

/**
 * Subscribe to live progress for an episode. Returns unsubscribe.
 * Immediately invokes listener with current snapshot if one exists.
 */
export function subscribeEpisodeAnalysisProgress(episodeId, listener) {
    const id = toEpisodeId(episodeId);
    if (!id || typeof listener !== 'function') return () => {};

    let listeners = analysisProgressListenersByEpisode.get(id);
    if (!listeners) {
        listeners = new Set();
        analysisProgressListenersByEpisode.set(id, listeners);
    }
    listeners.add(listener);

    const current = analysisProgressByEpisode.get(id);
    if (current) {
        try {
            listener(current);
        } catch (_) {
            // Ignore initial hydrate failures.
        }
    }

    return () => {
        const set = analysisProgressListenersByEpisode.get(id);
        if (!set) return;
        set.delete(listener);
        if (set.size === 0) analysisProgressListenersByEpisode.delete(id);
    };
}
