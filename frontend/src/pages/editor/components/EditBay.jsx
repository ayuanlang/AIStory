import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Scissors } from 'lucide-react';
import { ASSET_BASE_URL } from '../../../config';
import {
    burnShotFlowerText,
    fetchEpisodeShots,
    fetchScenes,
    generateSceneScore,
    mergeEditCut,
    recognizeEditSubtitles,
} from '../../../services/api';

const mediaSrc = (url) => {
    const raw = String(url || '').trim();
    if (!raw) return '';
    return raw.startsWith('http') ? raw : `${ASSET_BASE_URL}${raw}`;
};

const shotSortKey = (shot) => {
    const nums = String(shot?.shot_id || '').match(/\d+/g) || [];
    return nums.map((item) => Number(item));
};

const sceneSortKey = (scene) => {
    const nums = String(scene?.scene_no || '').match(/\d+/g) || [];
    return nums.length ? Number(nums[nums.length - 1]) : 9999;
};

const readCues = (shot) => {
    try {
        const notes = JSON.parse(shot?.technical_notes || '{}');
        return Array.isArray(notes?.edit_subtitles) ? notes.edit_subtitles : [];
    } catch {
        return [];
    }
};

const withCues = (shot, hit) => {
    if (!hit) return shot;
    let notes = {};
    try { notes = JSON.parse(shot.technical_notes || '{}'); } catch { notes = {}; }
    notes.edit_subtitles = hit.cues || [];
    notes.edit_subtitle_source = hit.source || '';
    notes.edit_subtitle_notice = hit.notice || '';
    return { ...shot, technical_notes: JSON.stringify(notes) };
};

const errorText = (error) => {
    const detail = error?.response?.data?.detail || error?.message || String(error || '');
    return typeof detail === 'string' ? detail : JSON.stringify(detail);
};

export const EditBay = ({
    activeEpisode,
    onLog,
    uiLang = 'zh',
    isReadOnly = false,
}) => {
    const t = (zh, en) => (uiLang === 'zh' ? zh : en);
    const [shots, setShots] = useState([]);
    const [scenes, setScenes] = useState([]);
    const [scope, setScope] = useState('episode');
    const [sceneId, setSceneId] = useState(0);
    const [busy, setBusy] = useState('');
    const [status, setStatus] = useState('');
    const [exportUrl, setExportUrl] = useState('');

    const load = useCallback(async () => {
        const episodeId = Number(activeEpisode?.id || 0);
        if (!episodeId) {
            setShots([]);
            setScenes([]);
            return;
        }
        const [shotRows, sceneRows] = await Promise.all([
            fetchEpisodeShots(episodeId, { limit: 500 }),
            fetchScenes(episodeId, { limit: 300 }).catch(() => []),
        ]);
        const sceneList = Array.isArray(sceneRows) ? sceneRows : [];
        const sceneById = new Map(sceneList.map((scene) => [Number(scene.id), scene]));
        const list = (Array.isArray(shotRows) ? shotRows : []).slice().sort((a, b) => {
            const sceneDelta = sceneSortKey(sceneById.get(Number(a?.scene_id))) - sceneSortKey(sceneById.get(Number(b?.scene_id)));
            if (sceneDelta) return sceneDelta;
            const left = shotSortKey(a);
            const right = shotSortKey(b);
            const length = Math.max(left.length, right.length);
            for (let index = 0; index < length; index += 1) {
                const delta = (left[index] || 0) - (right[index] || 0);
                if (delta) return delta;
            }
            return Number(a?.id || 0) - Number(b?.id || 0);
        });
        setShots(list);
        setScenes(sceneList);
    }, [activeEpisode?.id]);

    useEffect(() => {
        let cancelled = false;
        setExportUrl('');
        load().catch((error) => {
            if (!cancelled) setStatus(errorText(error));
        });
        return () => {
            cancelled = true;
        };
    }, [load]);

    const sceneById = useMemo(
        () => new Map(scenes.map((scene) => [Number(scene.id), scene])),
        [scenes],
    );
    const sceneName = (id) => {
        const scene = sceneById.get(Number(id));
        return scene?.scene_name || (scene?.scene_no ? t(`第${scene.scene_no}场`, `Scene ${scene.scene_no}`) : t('未分场', 'No scene'));
    };
    const sceneGroups = useMemo(() => {
        const groups = [];
        shots.forEach((shot) => {
            const id = Number(shot.scene_id || 0);
            const last = groups[groups.length - 1];
            if (!last || last.id !== id) groups.push({ id, shots: [shot] });
            else last.shots.push(shot);
        });
        return groups;
    }, [shots]);
    const activeSceneId = sceneGroups.some((group) => group.id === Number(sceneId))
        ? Number(sceneId)
        : (sceneGroups[0]?.id || 0);
    const scopedShots = scope === 'scene'
        ? (sceneGroups.find((group) => group.id === activeSceneId)?.shots || [])
        : shots;
    const scopeLabel = scope === 'scene' ? sceneName(activeSceneId) : t('本集', 'this episode');

    const patchShots = (rows) => {
        const byId = new Map(rows.map((shot) => [Number(shot.id), shot]));
        setShots((prev) => prev.map((shot) => byId.get(Number(shot.id)) || shot));
    };

    const recognizeList = async (list) => {
        const episodeId = Number(activeEpisode?.id || 0);
        const ids = list.map((shot) => Number(shot.id));
        if (!episodeId || !ids.length) return [];
        const systemApiId = Number(localStorage.getItem('func_api_script_analysis') || 0) || null;
        const hits = [];
        for (let index = 0; index < ids.length; index += 8) {
            const chunk = ids.slice(index, index + 8);
            setStatus(t(
                `正在识别${scopeLabel}字幕 ${Math.min(index + chunk.length, ids.length)}/${ids.length}`,
                `Recognizing ${scopeLabel} ${Math.min(index + chunk.length, ids.length)}/${ids.length}`,
            ));
            const result = await recognizeEditSubtitles(episodeId, {
                shot_ids: chunk,
                ...(systemApiId ? { system_api_id: systemApiId } : {}),
            });
            hits.push(...(result?.shots || []));
        }
        return hits;
    };

    const burnList = async (list) => {
        const targets = list.filter((shot) => readCues(shot).length && shot.video_url);
        const updated = [];
        for (let index = 0; index < targets.length; index += 1) {
            const shot = targets[index];
            setStatus(t(
                `正在烧录${scopeLabel} ${index + 1}/${targets.length}`,
                `Burning ${scopeLabel} ${index + 1}/${targets.length}`,
            ));
            const result = await burnShotFlowerText(shot.id, {
                lines: readCues(shot).map((cue) => ({
                    text: cue.text,
                    start: cue.start,
                    end: cue.end,
                    size: '中',
                    place: '中',
                })),
            });
            const url = result?.url || result?.shot?.video_url;
            if (url) {
                updated.push({ ...shot, video_url: url });
                patchShots(updated);
            }
        }
        return updated;
    };

    const scoreList = async (list) => {
        const episodeId = Number(activeEpisode?.id || 0);
        const markers = [...new Set(list.map((shot) => Number(shot.scene_id || 0)).filter(Boolean))]
            .map((id) => String(sceneById.get(id)?.scene_no || '').trim())
            .filter(Boolean);
        if (!episodeId || !markers.length) {
            throw new Error(t('这一范围还没有导入场景', 'This range has no imported scene'));
        }
        const systemApiId = Number(localStorage.getItem('func_api_generate_entity_reference_audio_audio') || 0) || null;
        for (let index = 0; index < markers.length; index += 1) {
            setStatus(t(
                `正在生成${scopeLabel}配乐 ${index + 1}/${markers.length}`,
                `Generating score ${index + 1}/${markers.length}`,
            ));
            await generateSceneScore(episodeId, {
                scene_marker: markers[index],
                ...(systemApiId ? { system_api_id: systemApiId, function_name: 'generate_entity_reference_audio_audio' } : {}),
            });
        }
        return markers.length;
    };

    const mergeList = async (list, withScore) => {
        const episodeId = Number(activeEpisode?.id || 0);
        const ids = list.filter((shot) => shot.video_url).map((shot) => Number(shot.id));
        if (!episodeId || !ids.length) {
            throw new Error(t('这一范围还没有成片', 'This range has no finished shots'));
        }
        setStatus(withScore
            ? t(`正在合并${scopeLabel}并铺配乐…`, `Merging ${scopeLabel} with score…`)
            : t(`正在合并${scopeLabel}…`, `Merging ${scopeLabel}…`));
        const result = await mergeEditCut(episodeId, { shot_ids: ids, with_score: Boolean(withScore) });
        setExportUrl(String(result?.url || ''));
        return result;
    };

    const recognize = async () => {
        if (!scopedShots.length) return;
        setBusy('subtitles');
        try {
            const hits = await recognizeList(scopedShots);
            const next = scopedShots.map((shot) => withCues(shot, hits.find((item) => Number(item.id) === Number(shot.id))));
            patchShots(next);
            const noticed = hits.find((item) => item.notice);
            setStatus(noticed?.notice || t(`已识别${scopeLabel} ${hits.length} 镜`, `Recognized ${hits.length} shot(s) in ${scopeLabel}`));
            onLog?.(t(`字幕识别完成 ${hits.length} 镜`, `Subtitle recognition finished for ${hits.length} shot(s)`), 'success');
        } catch (error) {
            setStatus(errorText(error));
        } finally {
            setBusy('');
        }
    };

    const burn = async () => {
        const targets = scopedShots.filter((shot) => readCues(shot).length && shot.video_url);
        if (!targets.length) {
            setStatus(t('先做字幕识别，并确认这些镜已有成片', 'Recognize subtitles first, and make sure the shots have video'));
            return;
        }
        setBusy('burn');
        try {
            const updated = await burnList(scopedShots);
            patchShots(updated);
            setStatus(t(`已烧录${scopeLabel} ${updated.length} 镜`, `Burned ${updated.length} shot(s) in ${scopeLabel}`));
            onLog?.(t(`后期烧录完成 ${updated.length} 镜`, `Burn finished for ${updated.length} shot(s)`), 'success');
        } catch (error) {
            setStatus(errorText(error));
        } finally {
            setBusy('');
        }
    };

    const score = async () => {
        setBusy('score');
        try {
            const count = await scoreList(scopedShots);
            setStatus(t(`已生成${scopeLabel} ${count} 场配乐`, `Generated ${count} score(s) for ${scopeLabel}`));
            onLog?.(t('配乐已生成', 'Score generated'), 'success');
        } catch (error) {
            setStatus(errorText(error));
        } finally {
            setBusy('');
        }
    };

    const merge = async (withScore) => {
        setBusy(withScore ? 'mix' : 'merge');
        try {
            const result = await mergeList(scopedShots, withScore);
            setStatus(result?.notice || t(`${scopeLabel}成片已生成`, 'Cut is ready'));
            onLog?.(t('剪辑成片已生成', 'Edit cut is ready'), 'success');
        } catch (error) {
            setStatus(errorText(error));
        } finally {
            setBusy('');
        }
    };

    const runAll = async () => {
        if (!scopedShots.length) return;
        setBusy('all');
        try {
            const hits = await recognizeList(scopedShots);
            let current = scopedShots.map((shot) => withCues(shot, hits.find((item) => Number(item.id) === Number(shot.id))));
            patchShots(current);
            const burned = await burnList(current);
            if (burned.length) {
                const burnedById = new Map(burned.map((shot) => [Number(shot.id), shot]));
                current = current.map((shot) => burnedById.get(Number(shot.id)) || shot);
                patchShots(current);
            }
            await scoreList(current);
            const result = await mergeList(current, true);
            setStatus(result?.notice || t(`${scopeLabel}已完成字幕、烧录、配乐和合并`, `${scopeLabel} subtitles, burn, score, and merge are done`));
            onLog?.(t(`${scopeLabel}剪辑已完成`, `Edit finished for ${scopeLabel}`), 'success');
        } catch (error) {
            setStatus(errorText(error));
        } finally {
            setBusy('');
        }
    };

    const buttonClass = 'px-3 py-1.5 rounded-md bg-white/10 hover:bg-white/20 text-xs font-semibold text-white disabled:opacity-40';
    const scopeClass = (active) => `px-3 py-1.5 rounded-md text-xs font-semibold disabled:opacity-40 ${active ? 'bg-white text-black' : 'bg-white/10 text-white hover:bg-white/20'}`;
    const visibleGroups = scope === 'scene'
        ? sceneGroups.filter((group) => group.id === activeSceneId)
        : sceneGroups;

    return (
        <div className="flex flex-col h-full min-h-0 p-4 gap-3">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                    <div className="flex items-center gap-2 text-sm font-bold text-white">
                        <Scissors className="w-4 h-4" />
                        {t('剪辑', 'Edit')}
                    </div>
                    <div className="text-[11px] text-white/45 mt-1 max-w-3xl">
                        {t(
                            '按整集或按一场，一次做完字幕识别、后期烧录、本场配乐和合并。识别优先走语音识别接口，没有结果时用分镜对白，再由大模型对齐到镜头时长。',
                            'Run subtitle recognition, burn-in, scene score, and merge for the whole episode or one scene. Recognition uses a speech API when available, otherwise the storyboard dialogue, then the model times the lines to each shot.'
                        )}
                    </div>
                </div>
                <div className="flex flex-col items-end gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                        <button type="button" className={scopeClass(scope === 'episode')} disabled={!!busy} onClick={() => setScope('episode')}>
                            {t('本集', 'Episode')}
                        </button>
                        <button type="button" className={scopeClass(scope === 'scene')} disabled={!!busy || !sceneGroups.length} onClick={() => setScope('scene')}>
                            {t('本场', 'Scene')}
                        </button>
                        {scope === 'scene' ? (
                            <select
                                className="bg-black/40 border border-white/10 rounded-md px-2 py-1.5 text-xs text-white"
                                value={activeSceneId || ''}
                                disabled={!!busy}
                                onChange={(event) => setSceneId(Number(event.target.value))}
                            >
                                {sceneGroups.map((group) => (
                                    <option key={group.id} value={group.id}>
                                        {sceneName(group.id)} · {group.shots.length}{t('镜', '')}
                                    </option>
                                ))}
                            </select>
                        ) : (
                            <span className="text-[11px] text-white/45">
                                {sceneGroups.length}{t('场', ' scenes')} · {shots.length}{t('镜', ' shots')}
                            </span>
                        )}
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                        <button type="button" className="px-3 py-1.5 rounded-md bg-white text-black text-xs font-semibold disabled:opacity-40" disabled={isReadOnly || !!busy || !scopedShots.length} onClick={runAll}>
                            {busy === 'all' ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : null}
                            {scope === 'scene' ? t('一次完成本场', 'Finish this scene') : t('一次完成本集', 'Finish this episode')}
                        </button>
                        <button type="button" className={buttonClass} disabled={isReadOnly || !!busy || !scopedShots.length} onClick={recognize}>
                            {busy === 'subtitles' ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : null}
                            {t('字幕识别', 'Recognize subtitles')}
                        </button>
                        <button type="button" className={buttonClass} disabled={isReadOnly || !!busy || !scopedShots.length} onClick={burn}>
                            {busy === 'burn' ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : null}
                            {t('后期烧录', 'Burn subtitles')}
                        </button>
                        <button type="button" className={buttonClass} disabled={isReadOnly || !!busy || !scopedShots.length} onClick={score}>
                            {busy === 'score' ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : null}
                            {t('配乐', 'Score')}
                        </button>
                        <button type="button" className={buttonClass} disabled={isReadOnly || !!busy || !scopedShots.length} onClick={() => merge(false)}>
                            {busy === 'merge' ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : null}
                            {t('合并', 'Merge')}
                        </button>
                        <button type="button" className={buttonClass} disabled={isReadOnly || !!busy || !scopedShots.length} onClick={() => merge(true)}>
                            {busy === 'mix' ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : null}
                            {t('合并并铺配乐', 'Merge with score')}
                        </button>
                    </div>
                </div>
            </div>
            {status ? <div className="text-xs text-white/70">{status}</div> : null}
            {exportUrl ? (
                <video controls src={mediaSrc(exportUrl)} className="w-full max-h-72 rounded-lg bg-black" />
            ) : null}
            <div className="flex-1 min-h-0 overflow-auto border border-white/10 rounded-lg">
                {shots.length === 0 ? (
                    <div className="p-6 text-xs text-white/40">{t('这一集还没有分镜。', 'This episode has no shots yet.')}</div>
                ) : visibleGroups.map((group) => (
                    <div key={group.id || 'none'}>
                        <div className="px-3 py-2 text-xs font-semibold text-white/80 bg-white/5 border-b border-white/10">
                            {sceneName(group.id)}
                            <span className="ml-2 font-normal text-white/40">{group.shots.length}{t('镜', ' shots')}</span>
                        </div>
                        {group.shots.map((shot) => {
                            const cues = readCues(shot);
                            return (
                                <div key={shot.id} className="px-3 py-2 border-b border-white/5 text-xs">
                                    <div className="text-white/85 font-semibold">
                                        {shot.shot_id || shot.id}
                                        <span className="ml-2 text-white/40 font-normal">{shot.duration || '—'}s</span>
                                        {!shot.video_url ? <span className="ml-2 text-amber-300/80">{t('无成片', 'No video')}</span> : null}
                                    </div>
                                    <div className="text-white/50 truncate">
                                        {cues.length
                                            ? cues.map((cue) => cue.text).join(' / ')
                                            : t('还没有字幕', 'No subtitles yet')}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ))}
            </div>
        </div>
    );
};
