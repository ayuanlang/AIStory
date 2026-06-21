import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, RotateCcw, X } from 'lucide-react';
import { fetchDeletionBatches, restoreDeletionBatch } from '../services/api';
import { confirmUiMessage } from '../lib/uiMessage';

const formatDeletionActionLabel = (actionType, t) => {
    const map = {
        project: t('项目', 'Project'),
        episode: t('分集', 'Episode'),
        scene: t('场景', 'Scene'),
        shot: t('分镜', 'Shot'),
        entity: t('主体', 'Entity'),
        asset: t('资产', 'Asset'),
        assets_batch: t('批量资产', 'Batch assets'),
        episode_entities: t('分集主体', 'Episode entities'),
    };
    return map[actionType] || actionType || t('删除', 'Delete');
};

export const DeletionTrashModal = ({
    open,
    onClose,
    projectId = null,
    uiLang = 'zh',
    onRestored = null,
}) => {
    const t = useCallback((zh, en) => (uiLang === 'zh' ? zh : en), [uiLang]);
    const [loading, setLoading] = useState(false);
    const [batches, setBatches] = useState([]);
    const [restoringBatchId, setRestoringBatchId] = useState(null);

    const loadBatches = useCallback(async () => {
        setLoading(true);
        try {
            const rows = await fetchDeletionBatches({
                projectId: projectId != null ? Number(projectId) : undefined,
                limit: 100,
            });
            setBatches(Array.isArray(rows) ? rows : []);
        } catch (error) {
            console.error('Failed to load deletion batches', error);
            setBatches([]);
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        if (open) {
            loadBatches();
        }
    }, [open, loadBatches]);

    const handleRestore = async (batchId) => {
        if (!batchId) return;
        if (!await confirmUiMessage(t('确定恢复该删除批次吗？', 'Restore this deletion batch?'))) return;
        setRestoringBatchId(batchId);
        try {
            await restoreDeletionBatch(batchId);
            await loadBatches();
            onRestored?.();
        } catch (error) {
            console.error('Failed to restore deletion batch', error);
            alert(t('恢复失败', error?.response?.data?.detail || error?.message || 'Failed to restore'));
        } finally {
            setRestoringBatchId(null);
        }
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="w-full max-w-3xl max-h-[80vh] overflow-hidden rounded-2xl border border-white/10 bg-card shadow-2xl flex flex-col">
                <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
                    <div>
                        <h2 className="text-lg font-semibold">{t('回收站', 'Recycle Bin')}</h2>
                        <p className="text-xs text-muted-foreground mt-1">
                            {t(
                                '按删除批次恢复已软删除的内容。',
                                'Restore soft-deleted items by deletion batch.',
                            )}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="p-2 rounded-lg hover:bg-secondary/60"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                    {loading ? (
                        <div className="flex items-center justify-center py-16 text-muted-foreground gap-2">
                            <Loader2 className="w-5 h-5 animate-spin" />
                            {t('加载中...', 'Loading...')}
                        </div>
                    ) : batches.length === 0 ? (
                        <div className="text-center py-16 text-muted-foreground">
                            {t('暂无可恢复的删除批次', 'No restorable deletion batches')}
                        </div>
                    ) : (
                        batches.map((batch) => (
                            <div
                                key={batch.id}
                                className="rounded-xl border border-white/10 bg-background/40 p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
                            >
                                <div className="min-w-0">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="text-sm font-medium">
                                            {formatDeletionActionLabel(batch.action_type, t)}
                                        </span>
                                        {batch.label && (
                                            <span className="text-sm text-foreground truncate">{batch.label}</span>
                                        )}
                                    </div>
                                    <div className="text-xs text-muted-foreground mt-1">
                                        {batch.project_title || `Project #${batch.project_id}`}
                                        {batch.episode_title ? ` · ${batch.episode_title}` : ''}
                                    </div>
                                    <div className="text-xs text-muted-foreground mt-1">
                                        {batch.created_at || ''} · {t('共', 'Total')} {batch.item_count || 0} {t('项', 'items')}
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    disabled={restoringBatchId === batch.id || batch.is_restored}
                                    onClick={() => handleRestore(batch.id)}
                                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50 shrink-0"
                                >
                                    {restoringBatchId === batch.id ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <RotateCcw className="w-4 h-4" />
                                    )}
                                    {t('恢复', 'Restore')}
                                </button>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
};
