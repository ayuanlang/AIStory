import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, Cpu, HardDrive, RefreshCw, Recycle, Radar } from 'lucide-react';
import {
  getAdminMemoryStats,
  postAdminMemoryReclaim,
  postAdminMemoryTracemalloc,
} from '../services/api';
import { confirmUiMessage, notifyUiMessage } from '../lib/uiMessage';
import { getUiLang, tUI } from '../lib/uiLang';

const formatDuration = (seconds) => {
  const safe = Math.max(0, Number(seconds || 0));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const s = Math.floor(safe % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

const pressureColor = (pressure) => {
  if (pressure === 'high') return 'text-red-300 border-red-500/30 bg-red-500/10';
  if (pressure === 'elevated') return 'text-amber-200 border-amber-500/30 bg-amber-500/10';
  return 'text-emerald-200 border-emerald-500/30 bg-emerald-500/10';
};

const StatCard = ({ label, value, hint, accent = 'text-primary' }) => (
  <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-1">
    <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
    <div className={`text-2xl font-semibold ${accent}`}>{value ?? '-'}</div>
    {hint ? <div className="text-xs text-gray-500">{hint}</div> : null}
  </div>
);

export default function MemoryMonitorAdmin() {
  const lang = getUiLang();
  const t = (zh, en) => tUI(lang, zh, en);

  const [stats, setStats] = useState(null);
  const [reclaimResult, setReclaimResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reclaiming, setReclaiming] = useState(false);
  const [togglingTrace, setTogglingTrace] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState('');

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getAdminMemoryStats({ include_tracemalloc: true });
      setStats(data || null);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || t('加载失败', 'Load failed'));
    } finally {
      setLoading(false);
    }
  }, [lang]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const timer = setInterval(() => {
      fetchStats();
    }, 15000);
    return () => clearInterval(timer);
  }, [autoRefresh, fetchStats]);

  const handleReclaim = async () => {
    const ok = await confirmUiMessage(
      t(
        '将执行：清理过期任务缓存 + gc.collect() +（Linux）malloc_trim。可能短暂卡顿，是否继续？',
        'This will prune expired job caches, run gc.collect(), and malloc_trim on Linux. May hitch briefly. Continue?'
      )
    );
    if (!ok) return;
    setReclaiming(true);
    setError('');
    try {
      const result = await postAdminMemoryReclaim({
        prune_caches: true,
        collect_gc: true,
        malloc_trim: true,
      });
      setReclaimResult(result || null);
      setStats(result?.after || null);
      const deltaMb = result?.delta?.rss_mb;
      notifyUiMessage(
        t(
          `回收完成。RSS 变化：${deltaMb == null ? '-' : `${deltaMb > 0 ? '+' : ''}${deltaMb} MB`}`,
          `Reclaim done. RSS delta: ${deltaMb == null ? '-' : `${deltaMb > 0 ? '+' : ''}${deltaMb} MB`}`
        ),
        'success'
      );
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || t('回收失败', 'Reclaim failed'));
    } finally {
      setReclaiming(false);
    }
  };

  const handleToggleTracemalloc = async () => {
    const enabled = !stats?.tracemalloc?.tracing;
    setTogglingTrace(true);
    try {
      const res = await postAdminMemoryTracemalloc({ enabled });
      notifyUiMessage(
        enabled
          ? t('已开启 tracemalloc（有额外开销）', 'tracemalloc enabled (extra overhead)')
          : t('已关闭 tracemalloc', 'tracemalloc disabled'),
        'success'
      );
      await fetchStats();
      if (res?.tracing !== enabled) {
        // keep UI honest
      }
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || t('切换失败', 'Toggle failed'));
    } finally {
      setTogglingTrace(false);
    }
  };

  const memory = stats?.memory || {};
  const cgroup = stats?.cgroup || {};
  const gcInfo = stats?.gc || {};
  const stores = stats?.stores?.items || [];
  const analysis = stats?.analysis || {};
  const tracemallocTop = stats?.tracemalloc?.top || [];

  const pressureLabel = useMemo(() => {
    const p = analysis.pressure || 'normal';
    if (p === 'high') return t('高压', 'High');
    if (p === 'elevated') return t('偏高', 'Elevated');
    return t('正常', 'Normal');
  }, [analysis.pressure, lang]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Cpu size={18} className="text-primary" />
            {t('内存监控', 'Memory Monitor')}
          </h2>
          <p className="text-xs text-gray-400 mt-1">
            {t(
              '查看进程 RSS、cgroup、GC、内存 store 估算，并支持主动回收分析。',
              'Inspect process RSS, cgroup, GC, in-memory store estimates, and trigger reclaim analysis.'
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <label className="flex items-center gap-2 text-xs text-gray-300 bg-white/5 border border-white/10 rounded-lg px-3 py-2">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            {t('15s 自动刷新', 'Auto-refresh 15s')}
          </label>
          <button
            onClick={fetchStats}
            disabled={loading}
            className="bg-white/10 text-white px-3 py-2 rounded-lg text-sm hover:bg-white/20 disabled:opacity-50 flex items-center gap-2"
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            {t('刷新', 'Refresh')}
          </button>
          <button
            onClick={handleReclaim}
            disabled={reclaiming}
            className="bg-primary text-black px-3 py-2 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
          >
            <Recycle size={15} className={reclaiming ? 'animate-spin' : ''} />
            {t('执行回收', 'Reclaim')}
          </button>
          <button
            onClick={handleToggleTracemalloc}
            disabled={togglingTrace}
            className="bg-white/10 text-white px-3 py-2 rounded-lg text-sm hover:bg-white/20 disabled:opacity-50 flex items-center gap-2"
          >
            <Radar size={15} />
            {stats?.tracemalloc?.tracing
              ? t('关闭 tracemalloc', 'Stop tracemalloc')
              : t('开启 tracemalloc', 'Start tracemalloc')}
          </button>
        </div>
      </div>

      {error ? (
        <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
          {String(error)}
        </div>
      ) : null}

      <div className={`rounded-xl border px-4 py-3 text-sm ${pressureColor(analysis.pressure)}`}>
        <div className="font-semibold mb-1">
          {t('压力等级', 'Pressure')}: {pressureLabel}
          {stats?.timestamp ? (
            <span className="ml-3 text-xs opacity-80">
              {t('采样时间', 'Sampled')}: {stats.timestamp}
            </span>
          ) : null}
        </div>
        <ul className="list-disc pl-5 space-y-1 text-xs opacity-95">
          {(analysis.tips || []).map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <StatCard
          label="RSS"
          value={memory.rss_mb != null ? `${memory.rss_mb} MB` : '-'}
          hint={memory.source ? `source: ${memory.source}` : undefined}
        />
        <StatCard
          label={t('虚拟内存', 'Virtual')}
          value={memory.vmsize_mb != null ? `${memory.vmsize_mb} MB` : '-'}
          hint={memory.peak_rss_mb != null ? `peak RSS ${memory.peak_rss_mb} MB` : undefined}
          accent="text-sky-300"
        />
        <StatCard
          label="cgroup"
          value={
            cgroup.current_mb != null
              ? `${cgroup.current_mb} MB`
              : t('不可用', 'N/A')
          }
          hint={
            cgroup.max_mb != null
              ? `max ${cgroup.max_mb} MB · ratio ${cgroup.usage_ratio != null ? `${Math.round(cgroup.usage_ratio * 100)}%` : '-'}`
              : t('非容器或无 cgroup 限制', 'No cgroup limit')
          }
          accent="text-violet-300"
        />
        <StatCard
          label={t('Store 估算', 'Store Estimate')}
          value={`${stats?.stores?.approx_total_mb ?? 0} MB`}
          hint={`${stores.length} stores · PID ${stats?.pid ?? '-'}`}
          accent="text-amber-200"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-2 lg:col-span-1">
          <div className="text-sm font-semibold text-white flex items-center gap-2">
            <Activity size={15} /> {t('进程信息', 'Process')}
          </div>
          <div className="text-xs text-gray-300 space-y-1.5">
            <div>PID: {stats?.pid ?? '-'}</div>
            <div>
              {t('运行时长', 'Uptime')}: {formatDuration(stats?.uptime_seconds)}
            </div>
            <div>
              {t('线程', 'Threads')}: {stats?.threads_active ?? '-'}
              {memory.proc_threads != null ? ` (proc ${memory.proc_threads})` : ''}
            </div>
            <div>FD: {stats?.open_fd ?? '-'}</div>
            <div>
              Python: {stats?.python_version || '-'} / {stats?.platform || '-'}
            </div>
            <div>Instance: {stats?.render?.instance_id || '-'}</div>
            <div>Commit: {stats?.render?.git_commit || '-'}</div>
          </div>
        </div>

        <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-2 lg:col-span-2">
          <div className="text-sm font-semibold text-white flex items-center gap-2">
            <Recycle size={15} /> {t('GC 状态', 'GC Status')}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-gray-300">
            <div>
              {t('启用', 'Enabled')}:{' '}
              <span className="text-white">{gcInfo.enabled ? 'yes' : 'no'}</span>
            </div>
            <div>
              counts: <span className="text-white">{(gcInfo.counts || []).join(' / ') || '-'}</span>
            </div>
            <div>
              thresholds:{' '}
              <span className="text-white">{(gcInfo.thresholds || []).join(' / ') || '-'}</span>
            </div>
            <div>
              tracked:{' '}
              <span className="text-white">{gcInfo.tracked_objects ?? '-'}</span>
            </div>
            <div>
              garbage:{' '}
              <span className="text-white">{gcInfo.garbage_objects ?? '-'}</span>
            </div>
            <div>
              freeze:{' '}
              <span className="text-white">{gcInfo.freeze_count ?? '-'}</span>
            </div>
          </div>
          {Array.isArray(gcInfo.stats) && gcInfo.stats.length > 0 ? (
            <div className="overflow-x-auto mt-2">
              <table className="w-full text-xs text-left">
                <thead className="text-gray-500">
                  <tr>
                    <th className="py-1 pr-3">gen</th>
                    <th className="py-1 pr-3">collections</th>
                    <th className="py-1 pr-3">collected</th>
                    <th className="py-1 pr-3">uncollectable</th>
                  </tr>
                </thead>
                <tbody className="text-gray-200">
                  {gcInfo.stats.map((row, idx) => (
                    <tr key={`gc-${idx}`} className="border-t border-white/5">
                      <td className="py-1.5 pr-3">{idx}</td>
                      <td className="py-1.5 pr-3">{row?.collections ?? '-'}</td>
                      <td className="py-1.5 pr-3">{row?.collected ?? '-'}</td>
                      <td className="py-1.5 pr-3">{row?.uncollectable ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>

      <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-3">
        <div className="text-sm font-semibold text-white flex items-center gap-2">
          <HardDrive size={15} /> {t('内存 Store 估算（采样外推）', 'In-memory Store Estimates (sampled)')}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="text-gray-500">
              <tr>
                <th className="py-1.5 pr-3">{t('名称', 'Name')}</th>
                <th className="py-1.5 pr-3">{t('条目', 'Items')}</th>
                <th className="py-1.5 pr-3">{t('采样', 'Sampled')}</th>
                <th className="py-1.5 pr-3">{t('估算', 'Approx')}</th>
              </tr>
            </thead>
            <tbody className="text-gray-200">
              {stores.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-3 text-gray-500">
                    {t('暂无 store 数据', 'No store data')}
                  </td>
                </tr>
              ) : (
                stores.map((row) => (
                  <tr key={row.name} className="border-t border-white/5">
                    <td className="py-1.5 pr-3 font-mono text-[11px]">{row.name}</td>
                    <td className="py-1.5 pr-3">{row.items ?? 0}</td>
                    <td className="py-1.5 pr-3">{row.sample_items ?? 0}</td>
                    <td className="py-1.5 pr-3">{row.approx_total_mb ?? 0} MB</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-gray-500">
          {t(
            '估算基于 JSON 序列化采样，用于相对对比，不是精确 RSS 分解。',
            'Estimates use JSON serialization sampling for relative comparison, not exact RSS attribution.'
          )}
        </p>
      </div>

      <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-3">
        <div className="text-sm font-semibold text-white flex items-center gap-2">
          <Radar size={15} /> tracemalloc
          <span className="text-xs text-gray-400 font-normal">
            {stats?.tracemalloc?.tracing
              ? t('跟踪中', 'tracing')
              : t('未开启', 'off')}
            {stats?.tracemalloc?.traced_current_mb != null
              ? ` · current ${stats.tracemalloc.traced_current_mb} MB / peak ${stats.tracemalloc.traced_peak_mb} MB`
              : ''}
          </span>
        </div>
        {!stats?.tracemalloc?.tracing ? (
          <p className="text-xs text-gray-500">
            {t(
              '开启后可查看按代码行的分配排行（有运行时开销，排查完请关闭）。',
              'Enable to see allocation tops by code line (runtime overhead; disable after debugging).'
            )}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="text-gray-500">
                <tr>
                  <th className="py-1.5 pr-3">{t('位置', 'Location')}</th>
                  <th className="py-1.5 pr-3">{t('大小', 'Size')}</th>
                  <th className="py-1.5 pr-3">{t('块数', 'Blocks')}</th>
                </tr>
              </thead>
              <tbody className="text-gray-200">
                {tracemallocTop.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-3 text-gray-500">
                      {t('暂无样本', 'No samples yet')}
                    </td>
                  </tr>
                ) : (
                  tracemallocTop.map((row) => (
                    <tr key={`${row.location}-${row.size_bytes}`} className="border-t border-white/5">
                      <td className="py-1.5 pr-3 font-mono text-[11px] break-all">{row.location || '-'}</td>
                      <td className="py-1.5 pr-3">{row.size_mb ?? 0} MB</td>
                      <td className="py-1.5 pr-3">{row.count ?? 0}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {reclaimResult ? (
        <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-2">
          <div className="text-sm font-semibold text-white">{t('最近一次回收结果', 'Last Reclaim Result')}</div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs text-gray-300">
            <div>
              RSS Δ:{' '}
              <span className="text-white">
                {reclaimResult?.delta?.rss_mb == null
                  ? '-'
                  : `${reclaimResult.delta.rss_mb > 0 ? '+' : ''}${reclaimResult.delta.rss_mb} MB`}
              </span>
            </div>
            <div>
              Store Δ:{' '}
              <span className="text-white">
                {reclaimResult?.delta?.store_approx_mb == null
                  ? '-'
                  : `${reclaimResult.delta.store_approx_mb > 0 ? '+' : ''}${reclaimResult.delta.store_approx_mb} MB`}
              </span>
            </div>
            <div>
              GC collected:{' '}
              <span className="text-white">{reclaimResult?.actions?.gc_collected ?? '-'}</span>
            </div>
            <div>
              malloc_trim:{' '}
              <span className="text-white">
                {reclaimResult?.actions?.malloc_trim ? 'yes' : 'no'}
              </span>
            </div>
          </div>
          <p className="text-[11px] text-gray-500">
            {t(
              '注意：Python 释放对象后 RSS 不一定立刻下降；Linux 上 malloc_trim 才更可能把页归还 OS。',
              'Note: RSS may not drop immediately after Python frees objects; malloc_trim on Linux is more likely to return pages to the OS.'
            )}
          </p>
        </div>
      ) : null}
    </div>
  );
}
