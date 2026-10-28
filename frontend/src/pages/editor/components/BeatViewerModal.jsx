import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Layers, X } from 'lucide-react';
import {
    BEAT_VIEWER_NODES,
    WHOLE_NODE_BEAT_ID,
    beatOptionLabel,
    buildBeatViewerScenes,
    findNodeBeat,
    matchWorkspaceScene,
    mergePipelineSceneBlocks,
    normalizeStoryboardShots,
    parseSceneSubskillResultsObject,
    shotOptionLabel,
    shotsCoveringBeat,
    splitStagingBeat,
} from '../beatViewer';

const nodeTitle = (node, t) => t(node.zh, node.en);

const ReadBlock = ({ text }) => (
    <div className="whitespace-pre-wrap break-words text-[12px] leading-6 text-white/80">
        {text}
    </div>
);

const StagingBeatBody = ({ beat, t }) => {
    const parts = splitStagingBeat(beat?.body || '');
    const sections = [
        { key: 'setup', label: t('建置', 'Setup'), text: parts.setup },
        { key: 'play', label: t('入戏', 'Action'), text: parts.play },
        { key: 'notes', label: t('场记分析', 'Continuity notes'), text: parts.notes },
    ].filter((section) => section.text);
    if (!sections.length) return <ReadBlock text={beat?.body || ''} />;
    return (
        <div className="flex flex-col gap-3">
            {sections.map((section) => (
                <div key={section.key} className="rounded-lg border border-white/10 bg-white/[0.03]">
                    <div className="border-b border-white/10 px-3 py-1.5 text-[11px] font-semibold tracking-wide text-sky-200/90">
                        {section.label}
                    </div>
                    <div className="px-3 py-2">
                        <ReadBlock text={section.text} />
                    </div>
                </div>
            ))}
        </div>
    );
};

const BeatBody = ({ node, beat, t }) => (
    node.key === 'staging'
        ? <StagingBeatBody beat={beat} t={t} />
        : <ReadBlock text={beat.body} />
);

const NodeColumn = ({ node, entries, sceneHasText, shotWithoutBeat, t }) => {
    const title = nodeTitle(node, t);
    const found = (entries || []).filter((entry) => entry.beat?.body);
    const chars = found.reduce((sum, entry) => sum + entry.beat.body.length, 0);
    let body = null;
    if (shotWithoutBeat) {
        body = (
            <div className="text-xs leading-6 text-white/35">
                {t('这镜的镜头逻辑里没有合镜Beat，对不上这一节点。', 'This shot has no merged-beat marker, so it cannot be traced to this node.')}
            </div>
        );
    } else if (found.length) {
        body = (
            <div className="flex flex-col gap-3">
                {entries.map((entry) => (
                    <div key={entry.id}>
                        {entries.length > 1 ? (
                            <div className="mb-1 text-[11px] font-semibold text-sky-200/80">{`Beat ${entry.id}`}</div>
                        ) : null}
                        {entry.beat?.body ? (
                            <BeatBody node={node} beat={entry.beat} t={t} />
                        ) : (
                            <div className="text-xs leading-6 text-white/35">
                                {sceneHasText
                                    ? t('这一节点没有这一拍。', 'This node has no draft for this beat.')
                                    : (node.key === 'combat'
                                        ? t('本场没有武戏增强成稿。', 'This scene has no action-enhancement draft.')
                                        : t('本场没有这一节点的成稿。', 'This scene has no draft for this node.'))}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        );
    } else if (!sceneHasText) {
        body = (
            <div className="text-xs leading-6 text-white/35">
                {node.key === 'combat'
                    ? t('本场没有武戏增强成稿。', 'This scene has no action-enhancement draft.')
                    : t('本场没有这一节点的成稿。', 'This scene has no draft for this node.')}
            </div>
        );
    } else {
        body = (
            <div className="text-xs leading-6 text-white/35">
                {t('这一节点没有这一拍。', 'This node has no draft for this beat.')}
            </div>
        );
    }
    return (
        <section className="flex h-[46vh] min-w-[280px] flex-1 flex-col overflow-hidden rounded-xl border border-white/10 bg-black/30 xl:h-full">
            <header className="flex items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
                <div className="min-w-0">
                    <div className="truncate text-sm font-bold text-white">{title}</div>
                    {node.key === 'staging' ? (
                        <div className="text-[10px] text-white/40">{t('含场记分析', 'Includes continuity notes')}</div>
                    ) : null}
                </div>
                <span className="shrink-0 text-[10px] text-white/35">
                    {chars ? t(`${chars} 字`, `${chars} chars`) : ''}
                </span>
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3 custom-scrollbar">
                {body}
            </div>
        </section>
    );
};

const StoryboardColumn = ({ shots, status, t }) => {
    let body = null;
    if (status === 'loading') {
        body = <div className="text-xs leading-6 text-white/35">{t('正在读取分镜…', 'Loading storyboards…')}</div>;
    } else if (!shots.length) {
        body = (
            <div className="text-xs leading-6 text-white/35">
                {status === 'unmatched'
                    ? t('没有分镜盖住这一拍。', 'No storyboard covers this beat.')
                    : status === 'missing'
                    ? t('工作区里还没有这场，分镜对不上。', 'This scene is not in the workspace, so there is no storyboard to trace.')
                    : status === 'error'
                        ? t('分镜没有读出来。', 'Storyboards could not be loaded.')
                        : t('本场还没有分镜。', 'This scene has no storyboard yet.')}
            </div>
        );
    } else {
        body = (
            <div className="flex flex-col gap-3">
                {shots.map((shot) => (
                    <div key={shot.key} className="rounded-lg border border-white/10 bg-white/[0.03]">
                        <div className="border-b border-white/10 px-3 py-1.5 text-[11px] font-semibold text-sky-200/90">
                            {shot.shotId}
                            {shot.beatIds.length
                                ? t(` · 覆盖 Beat ${shot.beatIds.join('、')}`, ` · covers Beat ${shot.beatIds.join(', ')}`)
                                : t(' · 未标拍', ' · no beat marker')}
                        </div>
                        <div className="flex flex-col gap-2 px-3 py-2">
                            {shot.logic ? (
                                <div>
                                    <div className="mb-1 text-[10px] font-semibold tracking-wide text-white/40">{t('镜头逻辑', 'Shot logic')}</div>
                                    <ReadBlock text={shot.logic} />
                                </div>
                            ) : null}
                            {shot.video ? (
                                <div>
                                    <div className="mb-1 text-[10px] font-semibold tracking-wide text-white/40">{t('视频内容', 'Video')}</div>
                                    <ReadBlock text={shot.video} />
                                </div>
                            ) : null}
                        </div>
                    </div>
                ))}
            </div>
        );
    }
    return (
        <section className="flex h-[46vh] min-w-[280px] flex-1 flex-col overflow-hidden rounded-xl border border-sky-400/20 bg-black/30 xl:h-full">
            <header className="flex items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
                <div className="min-w-0">
                    <div className="truncate text-sm font-bold text-white">{t('分镜生成', 'Storyboard')}</div>
                    <div className="text-[10px] text-white/40">{t('按合镜Beat回看上一拍', 'Trace back through 合镜Beat')}</div>
                </div>
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3 custom-scrollbar">
                {body}
            </div>
        </section>
    );
};

export default function BeatViewerModal({
    open,
    onClose,
    uiLang = 'zh',
    resultsRaw = '',
    pipelineNodes = [],
    workspaceScenes = [],
    fetchShots = null,
}) {
    const t = React.useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);
    const scenes = useMemo(() => {
        const stored = parseSceneSubskillResultsObject(resultsRaw);
        return buildBeatViewerScenes(mergePipelineSceneBlocks(stored, pipelineNodes));
    }, [pipelineNodes, resultsRaw]);
    const [sceneId, setSceneId] = useState('');
    const [beatId, setBeatId] = useState('');
    const [shotKey, setShotKey] = useState('');
    const [traceFromShot, setTraceFromShot] = useState(false);
    const [shots, setShots] = useState([]);
    const [shotsStatus, setShotsStatus] = useState('idle');

    useEffect(() => {
        if (!open) return undefined;
        const onKey = (event) => {
            if (event.key === 'Escape') onClose?.();
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onClose, open]);

    useEffect(() => {
        if (!open) return;
        setSceneId((prev) => (scenes.some((scene) => scene.sceneId === prev) ? prev : (scenes[0]?.sceneId || '')));
    }, [open, scenes]);

    const scene = scenes.find((item) => item.sceneId === sceneId) || null;
    const workspaceScene = useMemo(
        () => matchWorkspaceScene(workspaceScenes, sceneId),
        [sceneId, workspaceScenes],
    );
    const dbSceneId = Number(workspaceScene?.id || 0);

    useEffect(() => {
        if (!scene) {
            setBeatId('');
            return;
        }
        setBeatId((prev) => (scene.beatIds.includes(prev) ? prev : (scene.beatIds[0] || '')));
    }, [scene]);

    useEffect(() => {
        setShotKey('');
        setTraceFromShot(false);
    }, [sceneId]);

    useEffect(() => {
        if (!open || !sceneId) {
            setShots([]);
            setShotsStatus('idle');
            return undefined;
        }
        if (!dbSceneId || typeof fetchShots !== 'function') {
            setShots([]);
            setShotsStatus('missing');
            return undefined;
        }
        let cancelled = false;
        setShotsStatus('loading');
        fetchShots(dbSceneId)
            .then((rows) => {
                if (cancelled) return;
                setShots(normalizeStoryboardShots(rows));
                setShotsStatus('ready');
            })
            .catch(() => {
                if (cancelled) return;
                setShots([]);
                setShotsStatus('error');
            });
        return () => { cancelled = true; };
    }, [dbSceneId, fetchShots, open, sceneId]);

    if (!open) return null;

    const activeShot = shots.find((shot) => shot.key === shotKey) || null;
    const tracedBeatIds = (traceFromShot && activeShot)
        ? activeShot.beatIds
        : (beatId ? [beatId] : []);
    const displayShots = (traceFromShot && activeShot)
        ? [activeShot]
        : (beatId === WHOLE_NODE_BEAT_ID ? shots : shotsCoveringBeat(shots, beatId));
    const beatIndex = scene ? scene.beatIds.indexOf(beatId) : -1;
    const shotIndex = activeShot ? shots.findIndex((shot) => shot.key === activeShot.key) : -1;
    const chooseBeat = (nextId) => {
        setBeatId(nextId);
        setTraceFromShot(false);
        setShotKey('');
    };
    const chooseShot = (nextKey) => {
        if (!nextKey) {
            setShotKey('');
            setTraceFromShot(false);
            return;
        }
        const shot = shots.find((item) => item.key === nextKey);
        setShotKey(nextKey);
        setTraceFromShot(true);
        const first = shot?.beatIds?.[0];
        if (first && scene?.beatIds?.includes(first)) setBeatId(first);
    };
    const goBeat = (delta) => {
        if (!scene || beatIndex < 0) return;
        const next = scene.beatIds[beatIndex + delta];
        if (next) chooseBeat(next);
    };
    const goShot = (delta) => {
        if (!shots.length) return;
        if (shotIndex < 0) {
            if (delta > 0) chooseShot(shots[0].key);
            return;
        }
        const next = shots[shotIndex + delta];
        if (next) chooseShot(next.key);
    };
    const traceHint = (traceFromShot && activeShot)
        ? (activeShot.beatIds.length
            ? t(
                `${activeShot.shotId} 往前对应 Beat ${activeShot.beatIds.join('、')}`,
                `${activeShot.shotId} traces back to Beat ${activeShot.beatIds.join(', ')}`,
            )
            : t(
                `${activeShot.shotId} 的镜头逻辑里没有合镜Beat。`,
                `${activeShot.shotId} has no merged-beat marker in its shot logic.`,
            ))
        : (displayShots.length
            ? t(
                `Beat ${beatId} 落在 ${displayShots.map((shot) => shot.shotId).join('、')}`,
                `Beat ${beatId} lands in ${displayShots.map((shot) => shot.shotId).join(', ')}`,
            )
            : '');

    return (
        <div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-3 backdrop-blur-sm sm:p-6"
            onClick={() => onClose?.()}
        >
            <div
                className="flex h-[min(92vh,960px)] w-full max-w-[1680px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#141414] shadow-2xl"
                onClick={(event) => event.stopPropagation()}
            >
                <div className="flex items-start justify-between gap-3 border-b border-white/10 px-4 py-3 sm:px-5">
                    <div className="min-w-0">
                        <h3 className="flex items-center gap-2 text-lg font-bold text-white">
                            <Layers className="h-5 w-5 shrink-0 text-sky-300" />
                            {t('节拍查看器', 'Beat viewer')}
                        </h3>
                        <p className="mt-1 text-xs text-white/45">
                            {t(
                                '选节拍看四个上游节点和盖住它的分镜。选一镜时，按合镜Beat往前展开文戏、武戏、现场编排和建置与入戏。',
                                'Pick a beat to see the upstream nodes and the shots that cover it. Pick a shot to trace 合镜Beat back through drama, action, floor staging, and blocking.',
                            )}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => onClose?.()}
                        className="shrink-0 rounded-lg bg-white/10 px-3 py-1.5 text-sm font-bold text-white transition-colors hover:bg-white/20"
                        aria-label={t('关闭', 'Close')}
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <div className="flex flex-wrap items-center gap-2 border-b border-white/10 px-4 py-3 sm:px-5">
                    <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-[10px] font-semibold tracking-wide text-white/45">
                        {t('场景', 'Scene')}
                        <select
                            value={sceneId}
                            onChange={(event) => setSceneId(event.target.value)}
                            disabled={!scenes.length}
                            className="h-9 rounded-lg border border-white/10 bg-black/40 px-2 text-sm font-medium text-white outline-none focus:border-sky-400/50"
                        >
                            {!scenes.length ? (
                                <option value="">{t('暂无逐场成稿', 'No per-scene drafts')}</option>
                            ) : scenes.map((item) => (
                                <option key={item.sceneId} value={item.sceneId}>
                                    {item.name
                                        ? `${item.sceneId} · ${item.name} · ${item.beatIds.length}${t('拍', ' beats')}`
                                        : `${item.sceneId} · ${item.beatIds.length}${t('拍', ' beats')}`}
                                </option>
                            ))}
                        </select>
                    </label>
                    <label className="flex min-w-[220px] flex-[1.4] flex-col gap-1 text-[10px] font-semibold tracking-wide text-white/45">
                        {t('节拍', 'Beat')}
                        <select
                            value={beatId}
                            onChange={(event) => chooseBeat(event.target.value)}
                            disabled={!scene?.beatIds?.length}
                            className="h-9 rounded-lg border border-white/10 bg-black/40 px-2 text-sm font-medium text-white outline-none focus:border-sky-400/50"
                        >
                            {(scene?.beatIds || []).map((id) => (
                                <option key={id} value={id}>
                                    {id === WHOLE_NODE_BEAT_ID
                                        ? t('整段（未切拍）', 'Whole draft (no beat split)')
                                        : beatOptionLabel(scene, id)}
                                </option>
                            ))}
                        </select>
                    </label>
                    <div className="flex items-center gap-1 pt-4">
                        <button
                            type="button"
                            onClick={() => goBeat(-1)}
                            disabled={beatIndex <= 0}
                            className="inline-flex h-9 items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2.5 text-xs font-bold text-white/80 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                            <ChevronLeft className="h-3.5 w-3.5" />
                            {t('上一拍', 'Previous')}
                        </button>
                        <button
                            type="button"
                            onClick={() => goBeat(1)}
                            disabled={!scene || beatIndex < 0 || beatIndex >= scene.beatIds.length - 1}
                            className="inline-flex h-9 items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2.5 text-xs font-bold text-white/80 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                            {t('下一拍', 'Next')}
                            <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                    </div>
                    <label className="flex min-w-[240px] flex-[1.3] flex-col gap-1 text-[10px] font-semibold tracking-wide text-white/45">
                        {t('分镜', 'Shot')}
                        <select
                            value={traceFromShot ? shotKey : ''}
                            onChange={(event) => chooseShot(event.target.value)}
                            disabled={!shots.length}
                            className="h-9 rounded-lg border border-white/10 bg-black/40 px-2 text-sm font-medium text-white outline-none focus:border-sky-400/50"
                        >
                            <option value="">
                                {shots.length
                                    ? t('按当前节拍显示', 'Follow the current beat')
                                    : t('暂无分镜', 'No storyboard')}
                            </option>
                            {shots.map((shot) => (
                                <option key={shot.key} value={shot.key}>
                                    {shotOptionLabel(shot)}
                                </option>
                            ))}
                        </select>
                    </label>
                    <div className="flex items-center gap-1 pt-4">
                        <button
                            type="button"
                            onClick={() => goShot(-1)}
                            disabled={shotIndex <= 0}
                            className="inline-flex h-9 items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2.5 text-xs font-bold text-white/80 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                            <ChevronLeft className="h-3.5 w-3.5" />
                            {t('上一镜', 'Previous shot')}
                        </button>
                        <button
                            type="button"
                            onClick={() => goShot(1)}
                            disabled={!shots.length || (shotIndex >= 0 && shotIndex >= shots.length - 1)}
                            className="inline-flex h-9 items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2.5 text-xs font-bold text-white/80 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                            {t('下一镜', 'Next shot')}
                            <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                    </div>
                </div>
                {traceHint ? (
                    <div className="border-b border-white/10 px-4 py-2 text-xs text-sky-100/80 sm:px-5">
                        {traceHint}
                    </div>
                ) : null}

                <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4">
                    {!scenes.length ? (
                        <div className="flex h-full items-center justify-center px-6 text-center text-sm leading-6 text-white/45">
                            {t(
                                '还没有可查看的逐场成稿。完成文戏增强、武戏增强、现场编排、建置与入戏或分镜后，就可以按节拍对照。',
                                'No per-scene drafts yet. After drama, action, floor staging, blocking, or storyboards finish, beats can be compared here.',
                            )}
                        </div>
                    ) : (
                        <div className="flex h-full min-h-[46vh] gap-3 overflow-x-auto">
                            {BEAT_VIEWER_NODES.map((node) => (
                                <NodeColumn
                                    key={node.key}
                                    node={node}
                                    entries={tracedBeatIds.map((id) => ({
                                        id,
                                        beat: findNodeBeat(scene?.nodes?.[node.key], id),
                                    }))}
                                    sceneHasText={Boolean(scene?.nodes?.[node.key]?.text)}
                                    shotWithoutBeat={Boolean(traceFromShot && activeShot && !activeShot.beatIds.length)}
                                    t={t}
                                />
                            ))}
                            <StoryboardColumn
                                shots={displayShots}
                                status={shotsStatus === 'ready' && shots.length > 0 && displayShots.length === 0 ? 'unmatched' : shotsStatus}
                                t={t}
                            />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
