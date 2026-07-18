import React, { useEffect, useMemo, useState } from 'react';
import { Archive, RefreshCw, Trash2 } from 'lucide-react';
import { getAdminProjectRetentionCandidates, purgeAdminProjectRetention } from '../services/api';
import { getUiLang, tUI } from '../lib/uiLang';

const ProjectRetentionAdmin = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);

    const [retentionDays, setRetentionDays] = useState(60);
    const [requireSoftDeleted, setRequireSoftDeleted] = useState(false);
    const [candidates, setCandidates] = useState(null);
    const [selectedIds, setSelectedIds] = useState(() => new Set());
    const [isLoading, setIsLoading] = useState(false);
    const [isPurging, setIsPurging] = useState(false);
    const [error, setError] = useState('');
    const [lastResult, setLastResult] = useState(null);

    const projects = candidates?.projects || [];

    const fetchCandidates = async () => {
        setIsLoading(true);
        setError('');
        setLastResult(null);
        try {
            const payload = await getAdminProjectRetentionCandidates({
                retention_days: Number(retentionDays) || 60,
                require_soft_deleted: !!requireSoftDeleted,
            });
            setCandidates(payload || null);
            setSelectedIds(new Set());
        } catch (e) {
            setError(e?.response?.data?.detail || e.message || t('加载失败', 'Failed to load'));
            setCandidates(null);
            setSelectedIds(new Set());
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchCandidates();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const allSelected = useMemo(
        () => projects.length > 0 && projects.every((p) => selectedIds.has(p.project_id)),
        [projects, selectedIds]
    );

    const toggleAll = () => {
        if (allSelected) {
            setSelectedIds(new Set());
            return;
        }
        setSelectedIds(new Set(projects.map((p) => p.project_id)));
    };

    const toggleOne = (projectId) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(projectId)) next.delete(projectId);
            else next.add(projectId);
            return next;
        });
    };

    const handlePurge = async () => {
        const ids = Array.from(selectedIds);
        if (!ids.length) {
            alert(t('请先勾选要备份并删除的项目', 'Select projects to backup and delete first'));
            return;
        }
        const ok = window.confirm(
            t(
                `确认对选中的 ${ids.length} 个项目先备份再永久删除？此操作不可恢复（账单流水会保留）。`,
                `Backup then permanently delete ${ids.length} selected project(s)? This cannot be undone (billing history is kept).`
            )
        );
        if (!ok) return;

        setIsPurging(true);
        setError('');
        try {
            const result = await purgeAdminProjectRetention({
                project_ids: ids,
                retention_days: Number(retentionDays) || 60,
                require_soft_deleted: !!requireSoftDeleted,
            });
            setLastResult(result || null);
            alert(
                t(
                    `完成：已备份并删除 ${result?.purged_count || 0} 个项目；跳过 ${result?.skipped_count || 0}；失败 ${result?.errors?.length || 0}`,
                    `Done: purged ${result?.purged_count || 0}; skipped ${result?.skipped_count || 0}; errors ${result?.errors?.length || 0}`
                )
            );
            await fetchCandidates();
        } catch (e) {
            setError(e?.response?.data?.detail || e.message || t('备份删除失败', 'Backup/purge failed'));
        } finally {
            setIsPurging(false);
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                <div>
                    <h3 className="text-lg font-bold text-orange-300">
                        {t('闲置项目备份删除', 'Idle Project Backup & Delete')}
                    </h3>
                    <p className="text-xs text-gray-400 mt-1 max-w-3xl">
                        {t(
                            '手动流程：先按「无更新天数」列出候选项目，勾选后再执行「先备份再删除」。不会自动调度。会导出分集/场景/分镜/资产/实体等关联数据到项目备份目录，然后硬删除并清理媒体。',
                            'Manual flow: list projects with no updates, select them, then backup and delete. Not scheduled. Exports related episodes/scenes/shots/assets/entities, then hard-deletes DB rows and media.'
                        )}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                        {t('备份目录', 'Backup dir')}: {candidates?.project_backup_dir || '-'}
                        {' · '}
                        {t('截止', 'Cutoff')}: {candidates?.cutoff_at || '-'}
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <label className="text-xs text-gray-300 flex items-center gap-1">
                        {t('无更新天数', 'Idle days')}
                        <input
                            type="number"
                            min={1}
                            max={3650}
                            value={retentionDays}
                            onChange={(e) => setRetentionDays(e.target.value)}
                            className="w-20 bg-black/40 border border-white/10 rounded px-2 py-1 text-sm"
                        />
                    </label>
                    <label className="text-xs text-gray-300 flex items-center gap-2 bg-black/30 border border-white/10 rounded px-2 py-1">
                        <input
                            type="checkbox"
                            checked={!!requireSoftDeleted}
                            onChange={(e) => setRequireSoftDeleted(e.target.checked)}
                        />
                        {t('仅已软删除', 'Soft-deleted only')}
                    </label>
                    <button
                        onClick={fetchCandidates}
                        disabled={isLoading || isPurging}
                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                    >
                        <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
                        {t('列出候选', 'List Candidates')}
                    </button>
                    <button
                        onClick={handlePurge}
                        disabled={isLoading || isPurging || selectedIds.size === 0}
                        className="bg-red-600 hover:bg-red-500 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                    >
                        <Archive size={16} />
                        <Trash2 size={16} />
                        {isPurging
                            ? t('备份删除中...', 'Backing up & deleting...')
                            : t(`备份并删除所选 (${selectedIds.size})`, `Backup & Delete Selected (${selectedIds.size})`)}
                    </button>
                </div>
            </div>

            {error ? (
                <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded p-3">{error}</div>
            ) : null}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">{t('候选项目数', 'Candidates')}</div>
                    <div className="text-lg font-bold">{Number(candidates?.total_count || 0)}</div>
                </div>
                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">{t('已勾选', 'Selected')}</div>
                    <div className="text-lg font-bold">{selectedIds.size}</div>
                </div>
                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">{t('上次删除成功', 'Last purged')}</div>
                    <div className="text-lg font-bold">{Number(lastResult?.purged_count || 0)}</div>
                </div>
            </div>

            <div className="overflow-x-auto border border-white/10 rounded-lg max-h-[560px] overflow-y-auto">
                <table className="w-full text-sm">
                    <thead className="bg-black/40 sticky top-0">
                        <tr className="text-left text-gray-300">
                            <th className="px-3 py-2 w-10">
                                <input type="checkbox" checked={allSelected} onChange={toggleAll} disabled={!projects.length} />
                            </th>
                            <th className="px-3 py-2">ID</th>
                            <th className="px-3 py-2">{t('项目', 'Project')}</th>
                            <th className="px-3 py-2">{t('所有者', 'Owner')}</th>
                            <th className="px-3 py-2 text-right">{t('闲置天', 'Idle days')}</th>
                            <th className="px-3 py-2 text-right">{t('分集', 'Eps')}</th>
                            <th className="px-3 py-2 text-right">{t('场景', 'Scenes')}</th>
                            <th className="px-3 py-2 text-right">{t('分镜', 'Shots')}</th>
                            <th className="px-3 py-2 text-right">{t('实体', 'Entities')}</th>
                            <th className="px-3 py-2 text-right">{t('资产', 'Assets')}</th>
                            <th className="px-3 py-2">{t('状态', 'Status')}</th>
                            <th className="px-3 py-2">{t('最近活动', 'Last activity')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {projects.map((row) => (
                            <tr key={row.project_id} className="border-t border-white/5">
                                <td className="px-3 py-2">
                                    <input
                                        type="checkbox"
                                        checked={selectedIds.has(row.project_id)}
                                        onChange={() => toggleOne(row.project_id)}
                                    />
                                </td>
                                <td className="px-3 py-2 font-mono">{row.project_id}</td>
                                <td className="px-3 py-2">{row.title}</td>
                                <td className="px-3 py-2 text-gray-300">
                                    {row.owner_username || '-'}
                                    {row.owner_id != null ? (
                                        <span className="text-xs text-gray-500"> ({row.owner_id})</span>
                                    ) : null}
                                </td>
                                <td className="px-3 py-2 text-right font-mono">{row.idle_days ?? '-'}</td>
                                <td className="px-3 py-2 text-right">{row.episode_count}</td>
                                <td className="px-3 py-2 text-right">{row.scene_count}</td>
                                <td className="px-3 py-2 text-right">{row.shot_count}</td>
                                <td className="px-3 py-2 text-right">{row.entity_count}</td>
                                <td className="px-3 py-2 text-right">{row.asset_count}</td>
                                <td className="px-3 py-2">
                                    {row.is_deleted ? (
                                        <span className="text-orange-300">{t('已软删', 'Soft-deleted')}</span>
                                    ) : (
                                        <span className="text-gray-400">{t('活跃', 'Active')}</span>
                                    )}
                                </td>
                                <td className="px-3 py-2 whitespace-nowrap text-gray-300">
                                    {row.last_activity_at
                                        ? new Date(row.last_activity_at).toLocaleString()
                                        : '-'}
                                </td>
                            </tr>
                        ))}
                        {!isLoading && projects.length === 0 && (
                            <tr>
                                <td colSpan={12} className="px-3 py-6 text-center text-gray-400">
                                    {t('暂无符合条件的项目', 'No matching projects')}
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {lastResult?.errors?.length ? (
                <div className="text-sm text-red-200 bg-red-500/10 border border-red-500/30 rounded p-3">
                    <div className="font-bold mb-1">{t('失败明细', 'Errors')}</div>
                    <pre className="whitespace-pre-wrap break-all text-xs">
                        {JSON.stringify(lastResult.errors, null, 2)}
                    </pre>
                </div>
            ) : null}
        </div>
    );
};

export default ProjectRetentionAdmin;
