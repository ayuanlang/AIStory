import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Scale } from 'lucide-react';
import { getAdminBillingReconcileCandidates, runAdminBillingReconcile, runAdminBillingReconcileSingle } from '../services/api';
import { getUiLang, tUI } from '../lib/uiLang';

const statusLabel = (status, t) => {
    const map = {
        ok: t('已补齐', 'Reconciled'),
        query_no_usage: t('查询无用量', 'No usage'),
        query_empty: t('查询空响应', 'Empty query'),
        skipped_not_candidate: t('非候选', 'Not candidate'),
        skipped_not_found: t('未找到', 'Not found'),
        skipped_already_has_usage: t('已有用量', 'Already has usage'),
        skipped_no_task_id: t('无 taskId', 'No taskId'),
        skipped_no_api_key: t('无 API Key', 'No API key'),
        skipped_unsupported_provider: t('不支持供应商', 'Unsupported provider'),
        error: t('失败', 'Error'),
    };
    return map[status] || status || '-';
};

const BillingReconcileAdmin = () => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);

    const [lookbackDays, setLookbackDays] = useState(3);
    const [limit, setLimit] = useState(200);
    const [candidates, setCandidates] = useState(null);
    const [selectedIds, setSelectedIds] = useState(() => new Set());
    const [isLoading, setIsLoading] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [error, setError] = useState('');
    const [lastResult, setLastResult] = useState(null);
    
    // Single reconcile task states
    const [singleTaskProvider, setSingleTaskProvider] = useState('');
    const [singleTaskId, setSingleTaskId] = useState('');
    const [singleTaskLoading, setSingleTaskLoading] = useState(false);
    const [singleTaskResult, setSingleTaskResult] = useState(null);

    const rows = candidates?.candidates || [];

    const fetchCandidates = async () => {
        setIsLoading(true);
        setError('');
        try {
            const payload = await getAdminBillingReconcileCandidates({
                lookback_days: Number(lookbackDays) || 3,
                limit: Number(limit) || 200,
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
        () => rows.length > 0 && rows.every((r) => selectedIds.has(r.action_id)),
        [rows, selectedIds]
    );

    const toggleAll = () => {
        if (allSelected) {
            setSelectedIds(new Set());
            return;
        }
        setSelectedIds(new Set(rows.map((r) => r.action_id)));
    };

    const toggleOne = (actionId) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(actionId)) next.delete(actionId);
            else next.add(actionId);
            return next;
        });
    };

        const handleRunSingle = async () => {
        if (!singleTaskProvider || !singleTaskId) {
            alert(t('�����ṩ�̺�����ID', 'Please fill both provider and task ID'));
            return;
        }
        setSingleTaskLoading(true);
        setSingleTaskResult(null);
        setError('');
        try {
            const result = await runAdminBillingReconcileSingle({
                provider: singleTaskProvider,
                task_id: singleTaskId
            });
            setSingleTaskResult(result);
        } catch (e) {
            console.error(e);
            setError(e?.response?.data?.detail || e.message || t('���ʶ���ʧ��', 'Single Reconcile failed'));
        } finally {
            setSingleTaskLoading(false);
        }
    };

        const handleRunSingle = async () => {
        if (!singleTaskProvider || !singleTaskId) {
            alert(t('�����ṩ�̺�����ID', 'Please fill both provider and task ID'));
            return;
        }
        setSingleTaskLoading(true);
        setSingleTaskResult(null);
        setError('');
        try {
            const result = await runAdminBillingReconcileSingle({
                provider: singleTaskProvider,
                task_id: singleTaskId
            });
            setSingleTaskResult(result);
        } catch (e) {
            console.error(e);
            setError(e?.response?.data?.detail || e.message || t('���ʶ���ʧ��', 'Single Reconcile failed'));
        } finally {
            setSingleTaskLoading(false);
        }
    };

        const handleRunSingle = async () => {
        if (!singleTaskProvider || !singleTaskId) {
            alert(t('�����ṩ�̺�����ID', 'Please fill both provider and task ID'));
            return;
        }
        setSingleTaskLoading(true);
        setSingleTaskResult(null);
        setError('');
        try {
            const result = await runAdminBillingReconcileSingle({
                provider: singleTaskProvider,
                task_id: singleTaskId
            });
            setSingleTaskResult(result);
            fetchCandidates();
        } catch (e) {
            console.error(e);
            setError(e?.response?.data?.detail || e.message || t('���ʶ���ʧ��', 'Single Reconcile failed'));
        } finally {
            setSingleTaskLoading(false);
        }
    };

        const handleRunSingle = async () => {
        if (!singleTaskProvider || !singleTaskId) {
            alert(t('�����ṩ�̺�����ID', 'Please fill both provider and task ID'));
            return;
        }
        setSingleTaskLoading(true);
        setSingleTaskResult(null);
        setError('');
        try {
            const result = await runAdminBillingReconcileSingle({
                provider: singleTaskProvider,
                task_id: singleTaskId
            });
            setSingleTaskResult(result);
            fetchCandidates();
        } catch (e) {
            console.error(e);
            setError(e?.response?.data?.detail || e.message || t('���ʶ���ʧ��', 'Single Reconcile failed'));
        } finally {
            setSingleTaskLoading(false);
        }
    };

    const handleRun = async () => {
        const ids = Array.from(selectedIds);
        if (!ids.length) {
            alert(t('请先勾选要对账的记录', 'Select records to reconcile first'));
            return;
        }
        const ok = window.confirm(
            t(
                `确认对选中的 ${ids.length} 条记录向供应商查询实际用量并回填？不会重新结算钱包。`,
                `Query providers and backfill actual usage for ${ids.length} selected record(s)? Wallet will not be re-settled.`
            )
        );
        if (!ok) return;

        setIsRunning(true);
        setError('');
        setLastResult(null);
        try {
            const result = await runAdminBillingReconcile({
                action_ids: ids,
                lookback_days: Number(lookbackDays) || 3,
            });
            setLastResult(result || null);
            await fetchCandidates();
        } catch (e) {
            setError(e?.response?.data?.detail || e.message || t('对账失败', 'Reconcile failed'));
        } finally {
            setIsRunning(false);
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                <div>
                    <h3 className="text-lg font-bold text-cyan-300">
                        {t('供应商用量对账', 'Supplier Usage Reconcile')}
                    </h3>
                    <p className="text-xs text-gray-400 mt-1 max-w-3xl">
                        {t(
                            '手工流程：列出近 N 天缺少供应商实际用量（KIE credits / API tokens / RunningHub 费用）的 API 流水，勾选后向供应商查询并回填审计字段。夜间任务也会自动跑；此处不改钱包扣费。',
                            'Manual flow: list API txs in last N days missing actual supplier usage, select and query providers to backfill audit fields. Nightly job also runs this; wallet charges are not changed.'
                        )}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                        {t('截止', 'Cutoff')}: {candidates?.cutoff_at || '-'}
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <label className="text-xs text-gray-300 flex items-center gap-1">
                        {t('回溯天数', 'Lookback days')}
                        <input
                            type="number"
                            min={1}
                            max={90}
                            value={lookbackDays}
                            onChange={(e) => setLookbackDays(e.target.value)}
                            className="w-20 bg-black/40 border border-white/10 rounded px-2 py-1 text-sm"
                        />
                    </label>
                    <label className="text-xs text-gray-300 flex items-center gap-1">
                        {t('上限', 'Limit')}
                        <input
                            type="number"
                            min={1}
                            max={2000}
                            value={limit}
                            onChange={(e) => setLimit(e.target.value)}
                            className="w-24 bg-black/40 border border-white/10 rounded px-2 py-1 text-sm"
                        />
                    </label>
                    <button
                        onClick={fetchCandidates}
                        disabled={isLoading || isRunning}
                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                    >
                        <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
                        {t('列出需对账', 'List Candidates')}
                    </button>
                    <button
                        onClick={handleRun}
                        disabled={isLoading || isRunning || selectedIds.size === 0}
                        className="bg-cyan-700 hover:bg-cyan-600 text-white px-3 py-2 rounded flex items-center gap-2 disabled:opacity-50"
                    >
                        <Scale size={16} />
                        {isRunning
                            ? t('对账中...', 'Reconciling...')
                            : t(`启动对账 (${selectedIds.size})`, `Start Reconcile (${selectedIds.size})`)}
                    </button>
                </div>
            </div>

            {error ? (
                <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded p-3">{error}</div>
            ) : null}

                        <div className="bg-black/30 border border-white/10 rounded-lg p-3 w-full">
                <h4 className="text-sm font-bold text-gray-200 mb-2">{t('���ʶ���', 'Single Reconcile')}</h4>
                <div className="flex flex-wrap gap-2 items-center text-xs">
                    <input
                        type="text"
                        placeholder={t('��Ӧ��', 'Provider')}
                        value={singleTaskProvider}
                        onChange={(e) => setSingleTaskProvider(e.target.value)}
                        className="bg-black/40 border border-white/10 rounded px-2 py-1 flex-1 min-w-[150px]"
                    />
                    <input
                        type="text"
                        placeholder="taskId"
                        value={singleTaskId}
                        onChange={(e) => setSingleTaskId(e.target.value)}
                        className="bg-black/40 border border-white/10 rounded px-2 py-1 flex-1 min-w-[200px]"
                    />
                    <button
                        onClick={handleRunSingle}
                        disabled={singleTaskLoading || !singleTaskProvider || !singleTaskId}
                        className="bg-cyan-700 hover:bg-cyan-600 text-white px-4 py-1 rounded disabled:opacity-50"
                    >
                        {singleTaskLoading ? t('������...', '...') : t('ִ��', 'Run')}
                    </button>
                </div>
                {singleTaskResult && (
                    <div className={mt-3 p-2 rounded text-xs }>
                        {singleTaskResult.status === 'ok' || singleTaskResult.ok ? t('���˳ɹ�: �����Ѳ���', 'Success: Usage recorded') : ${t('����ʧ��', 'Failed')}: }
                        {(singleTaskResult.status === 'ok' || singleTaskResult.ok) && singleTaskResult.usage && (
                           <div className="mt-1 text-[10px] text-gray-500 break-all">
                               {JSON.stringify(singleTaskResult.usage)}
                           </div>
                        )}
                    </div>
                )}
            </div>

                        <div className="bg-black/30 border border-white/10 rounded-lg p-3 w-full">
                <h4 className="text-sm font-bold text-gray-200 mb-2">{t('���ʶ���', 'Single Reconcile')}</h4>
                <div className="flex flex-wrap gap-2 items-center text-xs">
                    <input
                        type="text"
                        placeholder={t('��Ӧ��', 'Provider')}
                        value={singleTaskProvider}
                        onChange={(e) => setSingleTaskProvider(e.target.value)}
                        className="bg-black/40 border border-white/10 rounded px-2 py-1 flex-1 min-w-[150px]"
                    />
                    <input
                        type="text"
                        placeholder="taskId"
                        value={singleTaskId}
                        onChange={(e) => setSingleTaskId(e.target.value)}
                        className="bg-black/40 border border-white/10 rounded px-2 py-1 flex-1 min-w-[200px]"
                    />
                    <button
                        onClick={handleRunSingle}
                        disabled={singleTaskLoading || !singleTaskProvider || !singleTaskId}
                        className="bg-cyan-700 hover:bg-cyan-600 text-white px-4 py-1 rounded disabled:opacity-50"
                    >
                        {singleTaskLoading ? t('������...', '...') : t('ִ��', 'Run')}
                    </button>
                </div>
                {singleTaskResult && (
                    <div className={mt-3 p-2 rounded text-xs }>
                        {singleTaskResult.status === 'ok' || singleTaskResult.ok ? t('���˳ɹ�: �����Ѳ���', 'Success: Usage recorded') : ${t('����ʧ��', 'Failed')}: }
                        {(singleTaskResult.status === 'ok' || singleTaskResult.ok) && singleTaskResult.usage && (
                           <div className="mt-1 text-[10px] text-gray-500 break-all">
                               {JSON.stringify(singleTaskResult.usage)}
                           </div>
                        )}
                    </div>
                )}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">{t('需对账', 'Candidates')}</div>
                    <div className="text-lg font-bold">{Number(candidates?.total_count || 0)}</div>
                </div>
                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">{t('已勾选', 'Selected')}</div>
                    <div className="text-lg font-bold">{selectedIds.size}</div>
                </div>
                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">{t('上次成功', 'Last OK')}</div>
                    <div className="text-lg font-bold text-green-300">{Number(lastResult?.reconciled_ok || 0)}</div>
                </div>
                <div className="bg-black/30 border border-white/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">{t('上次跳过/失败', 'Last skip/err')}</div>
                    <div className="text-lg font-bold">
                        {Number(lastResult?.skipped_count || 0)} / {Number(lastResult?.error_count || 0)}
                    </div>
                </div>
            </div>

            <div className="overflow-x-auto border border-white/10 rounded-lg max-h-[420px] overflow-y-auto">
                <table className="w-full text-sm">
                    <thead className="bg-black/40 sticky top-0">
                        <tr className="text-left text-gray-300">
                            <th className="px-3 py-2 w-10">
                                <input type="checkbox" checked={allSelected} onChange={toggleAll} disabled={!rows.length} />
                            </th>
                            <th className="px-3 py-2">Action</th>
                            <th className="px-3 py-2">Tx</th>
                            <th className="px-3 py-2">{t('用户', 'User')}</th>
                            <th className="px-3 py-2">{t('类型', 'Type')}</th>
                            <th className="px-3 py-2">{t('供应商', 'Provider')}</th>
                            <th className="px-3 py-2">Model</th>
                            <th className="px-3 py-2">taskId</th>
                            <th className="px-3 py-2 text-right">{t('预扣/实扣', 'Reserved/Actual')}</th>
                            <th className="px-3 py-2">{t('缺失', 'Missing')}</th>
                            <th className="px-3 py-2">{t('时间', 'Time')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row) => (
                            <tr key={row.action_id} className="border-t border-white/5">
                                <td className="px-3 py-2">
                                    <input
                                        type="checkbox"
                                        checked={selectedIds.has(row.action_id)}
                                        onChange={() => toggleOne(row.action_id)}
                                    />
                                </td>
                                <td className="px-3 py-2 font-mono">{row.action_id}</td>
                                <td className="px-3 py-2 font-mono">{row.transaction_id ?? '-'}</td>
                                <td className="px-3 py-2 font-mono">{row.user_id ?? '-'}</td>
                                <td className="px-3 py-2">
                                    <div>{row.task_type || '-'}</div>
                                    <div className="text-xs text-gray-500">{row.stage || ''}</div>
                                </td>
                                <td className="px-3 py-2">{row.provider || '-'}</td>
                                <td className="px-3 py-2 max-w-[160px] truncate" title={row.model || ''}>
                                    {row.model || '-'}
                                </td>
                                <td className="px-3 py-2 font-mono text-xs max-w-[180px] truncate" title={row.task_id || ''}>
                                    {row.has_task_id ? row.task_id : (
                                        <span className="text-orange-300">{t('缺失', 'missing')}</span>
                                    )}
                                </td>
                                <td className="px-3 py-2 text-right font-mono">
                                    {row.reserved_cost}/{row.actual_cost}
                                </td>
                                <td className="px-3 py-2 text-xs text-amber-200">
                                    {(row.missing_reasons || []).join(', ') || '-'}
                                </td>
                                <td className="px-3 py-2 whitespace-nowrap text-gray-300">
                                    {row.created_at ? new Date(row.created_at).toLocaleString() : '-'}
                                </td>
                            </tr>
                        ))}
                        {!isLoading && rows.length === 0 && (
                            <tr>
                                <td colSpan={11} className="px-3 py-6 text-center text-gray-400">
                                    {t('暂无需要对账的记录', 'No records need reconcile')}
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {lastResult ? (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                    <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                        <div className="font-bold text-sm mb-2">{t('对账过程', 'Process Log')}</div>
                        <div className="max-h-[280px] overflow-y-auto space-y-1 text-xs font-mono">
                            {(lastResult.process_log || []).map((item, idx) => (
                                <div key={`${item.ts || 't'}-${idx}`} className="border-b border-white/5 pb-1 text-gray-300">
                                    <span className="text-cyan-300">{item.ts || '-'}</span>
                                    {' · '}
                                    <span className="text-white">{item.step}</span>
                                    {item.action_id != null ? ` · action=${item.action_id}` : ''}
                                    {item.status ? ` · ${item.status}` : ''}
                                    {item.provider ? ` · ${item.provider}` : ''}
                                    {item.task_id ? ` · task=${item.task_id}` : ''}
                                    {item.kie_credits != null ? ` · kie=${item.kie_credits}` : ''}
                                    {item.total_tokens != null ? ` · tokens=${item.total_tokens}` : ''}
                                    {item.consumeMoney != null ? ` · money=${item.consumeMoney}` : ''}
                                    {item.consumeCoins != null ? ` · coins=${item.consumeCoins}` : ''}
                                    {item.error ? ` · err=${item.error}` : ''}
                                    {item.reason ? ` · ${item.reason}` : ''}
                                </div>
                            ))}
                            {!lastResult.process_log?.length ? (
                                <div className="text-gray-500">{t('无过程日志', 'No process log')}</div>
                            ) : null}
                        </div>
                    </div>
                    <div className="border border-white/10 rounded-lg p-3 bg-black/20">
                        <div className="font-bold text-sm mb-2">{t('对账结果', 'Results')}</div>
                        <div className="overflow-x-auto max-h-[280px] overflow-y-auto">
                            <table className="w-full text-xs">
                                <thead className="sticky top-0 bg-black/40 text-gray-300">
                                    <tr>
                                        <th className="px-2 py-1 text-left">Action</th>
                                        <th className="px-2 py-1 text-left">{t('状态', 'Status')}</th>
                                        <th className="px-2 py-1 text-left">{t('供应商', 'Provider')}</th>
                                        <th className="px-2 py-1 text-left">taskId</th>
                                        <th className="px-2 py-1 text-right">KIE</th>
                                        <th className="px-2 py-1 text-right">Tokens</th>
                                        <th className="px-2 py-1 text-right">Money/Coins</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(lastResult.results || []).map((row) => (
                                        <tr key={`r-${row.action_id}-${row.status}`} className="border-t border-white/5">
                                            <td className="px-2 py-1 font-mono">{row.action_id}</td>
                                            <td className="px-2 py-1">{statusLabel(row.status, t)}</td>
                                            <td className="px-2 py-1">{row.provider || '-'}</td>
                                            <td className="px-2 py-1 font-mono max-w-[140px] truncate" title={row.task_id || ''}>
                                                {row.task_id || '-'}
                                            </td>
                                            <td className="px-2 py-1 text-right font-mono">{row.kie_credits ?? '-'}</td>
                                            <td className="px-2 py-1 text-right font-mono">{row.total_tokens ?? '-'}</td>
                                            <td className="px-2 py-1 text-right font-mono">
                                                {row.consumeMoney ?? '-'} / {row.consumeCoins ?? '-'}
                                            </td>
                                        </tr>
                                    ))}
                                    {!lastResult.results?.length ? (
                                        <tr>
                                            <td colSpan={7} className="px-2 py-4 text-center text-gray-500">
                                                {t('无结果', 'No results')}
                                            </td>
                                        </tr>
                                    ) : null}
                                </tbody>
                            </table>
                        </div>
                        {lastResult.errors?.length ? (
                            <pre className="mt-2 text-xs text-red-200 whitespace-pre-wrap break-all">
                                {JSON.stringify(lastResult.errors, null, 2)}
                            </pre>
                        ) : null}
                    </div>
                </div>
            ) : null}
        </div>
    );
};

export default BillingReconcileAdmin;
