const analysisRunsByEpisode = new Map();

export function trackEpisodeAnalysisRun(episodeId, runPromise, meta = {}) {
    const id = Number(episodeId || 0);
    if (!id || !runPromise) return null;

    const entry = {
        episodeId: id,
        promise: runPromise,
        startedAt: Number(meta.startedAt || Date.now()),
        kind: String(meta.kind || 'analysis'),
        phase: meta.phase ?? 1,
        taskId: String(meta.taskId || '').trim(),
    };
    analysisRunsByEpisode.set(id, entry);

    runPromise.finally(() => {
        const current = analysisRunsByEpisode.get(id);
        if (current?.promise === runPromise) {
            analysisRunsByEpisode.delete(id);
        }
    });

    return entry;
}

export function getEpisodeAnalysisRun(episodeId) {
    const id = Number(episodeId || 0);
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
    const id = Number(episodeId || 0);
    if (!id) return;
    const current = analysisRunsByEpisode.get(id);
    if (!current) return;
    if (runPromise && current.promise !== runPromise) return;
    analysisRunsByEpisode.delete(id);
}
