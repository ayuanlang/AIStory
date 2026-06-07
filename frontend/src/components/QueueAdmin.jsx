import React, { useState, useEffect } from 'react';
import { RefreshCw, Trash2, StopCircle, Clock, PlayCircle, Loader2, Save, X } from 'lucide-react';
import { getAdminQueueTasks, cancelAdminQueueTask, cancelAllQueuedAdminTasks, getAdminQueueConfig, getAdminQueueStats, updateAdminQueueConfig, getSystemSettingsManage } from '../services/api';
import { confirmUiMessage, notifyUiMessage } from '../lib/uiMessage';

export default function QueueAdmin() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState({
    queue_threads: 10,
    callback_threads: 10,
    pure_callback_mode_auto: true,
    pure_callback_mode: false,
    callback_loss_retry_enabled: true,
    callback_loss_retry_after_seconds: 1800,
    callback_loss_max_submit_retries: 1,
    callback_compensation_scan_enabled: true,
    callback_compensation_scan_interval_seconds: 60,
    callback_compensation_scan_batch_size: 10,
  });
  const [savingConfig, setSavingConfig] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [systemApis, setSystemApis] = useState([]);
  const [queueStats, setQueueStats] = useState(null);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const res = await getAdminQueueTasks();
      setTasks(res.tasks || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchConfig = async () => {
    try {
      const dbConfig = await getAdminQueueConfig();
      setConfig(dbConfig);
    } catch(e) {}
  };

  const fetchSystemApis = async () => {
    try {
      const dbApis = await getSystemSettingsManage();
      setSystemApis(Array.isArray(dbApis) ? dbApis : []);
    } catch(e) {}
  };

  const fetchStats = async () => {
    try {
      const stats = await getAdminQueueStats();
      setQueueStats(stats || null);
    } catch(e) {}
  };

  const formatDuration = (seconds) => {
    const safe = Number(seconds || 0);
    if (!safe || safe < 1) return '0s';
    const h = Math.floor(safe / 3600);
    const m = Math.floor((safe % 3600) / 60);
    const s = Math.floor(safe % 60);
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };

  const refreshAll = async () => {
    await Promise.all([fetchTasks(), fetchStats()]);
  };

  const resolvePureCallbackRuntime = () => {
    const polling = queueStats?.polling || {};
    const effective = Boolean(polling.pure_callback_mode_effective);
    const startupMode = String(polling.startup_mode || '').trim();
    let source = '未知';
    if (startupMode === 'auto_public') source = '自动模式(公网部署)';
    else if (startupMode === 'auto_local') source = '自动模式(本地/非公网)';
    else if (startupMode === 'manual_on') source = '手动模式(开启)';
    else if (startupMode === 'manual_off') source = '手动模式(关闭)';
    return {
      effective,
      source,
      text: effective ? '当前运行: 纯回调模式' : '当前运行: 轮询模式',
    };
  };

  useEffect(() => {
    fetchTasks();
    fetchStats();
    fetchConfig();
    fetchSystemApis();
    const timer = setInterval(() => {
      fetchTasks();
      fetchStats();
    }, 30000);
    return () => clearInterval(timer);
  }, []);

  const getApiName = (apiId) => {
    if (!apiId) return null;
    const found = systemApis.find(a => a.id === apiId);
    return found ? found.name : `ID: ${apiId}`;
  };

  const handleSaveConfig = async () => {
    setSavingConfig(true);
    try {
      await updateAdminQueueConfig({
        queue_threads: Number(config.queue_threads),
        callback_threads: Number(config.callback_threads),
        pure_callback_mode_auto: Boolean(config.pure_callback_mode_auto),
        pure_callback_mode: Boolean(config.pure_callback_mode),
        callback_loss_retry_enabled: Boolean(config.callback_loss_retry_enabled),
        callback_loss_retry_after_seconds: Number(config.callback_loss_retry_after_seconds),
        callback_loss_max_submit_retries: Number(config.callback_loss_max_submit_retries),
        callback_compensation_scan_enabled: Boolean(config.callback_compensation_scan_enabled),
        callback_compensation_scan_interval_seconds: Number(config.callback_compensation_scan_interval_seconds),
        callback_compensation_scan_batch_size: Number(config.callback_compensation_scan_batch_size),
      });
      notifyUiMessage('Configuration saved. Some changes require a backend restart to fully apply.', 'success');
    } catch (e) {
      notifyUiMessage('Failed to save config', 'error');
    } finally {
      setSavingConfig(false);
    }
  };

  const handleCancel = async (jobId) => {
    if (await confirmUiMessage('Confirm cancellation?')) {
      try {
        await cancelAdminQueueTask(jobId);
        fetchTasks();
      } catch (e) {}
    }
  };

  const handleCancelAll = async () => {
    if (await confirmUiMessage('Cancel ALL queued tasks?')) {
      try {
        await cancelAllQueuedAdminTasks();
        fetchTasks();
      } catch (e) {}
    }
  };

  const pureCallbackRuntime = resolvePureCallbackRuntime();

  return (
    <div className="p-6 max-w-7xl mx-auto text-white space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Generation Task Queue</h2>
          <p className="text-gray-400 mt-1">Monitor and manage background LLM/Image tasks.</p>
        </div>
        <div className="flex gap-3">
          <button onClick={handleCancelAll} className="flex items-center gap-2 px-4 py-2 bg-red-600/20 text-red-500 rounded-lg hover:bg-red-600/40 transition-colors">
            <StopCircle size={18} /> Cancel All Queued
          </button>
          <button onClick={refreshAll} className="flex items-center gap-2 px-4 py-2 bg-white/10 rounded-lg hover:bg-white/20 transition-colors">
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-2">
          <div className="text-xs text-gray-400">任务队列</div>
          <div className="text-2xl font-bold text-blue-300">{queueStats?.runtime?.queue?.active_count ?? 0}</div>
          <div className="text-xs text-gray-500">活动任务(queued + running)</div>
          <div className="text-xs text-cyan-300">工作位 已用/总量/可用: {queueStats?.runtime?.queue?.worker_slots_in_use ?? 0} / {queueStats?.runtime?.queue?.worker_slots_total ?? 0} / {queueStats?.runtime?.queue?.worker_slots_available ?? 0}</div>
          <div className="text-xs text-gray-300">Queued: {queueStats?.runtime?.queue?.status_counts?.queued ?? 0} | Running: {queueStats?.runtime?.queue?.status_counts?.running ?? 0}</div>
          <div className="text-xs text-gray-300">最近1小时完成: {queueStats?.runtime?.queue?.finished_last_hour ?? 0}</div>
          <div className="text-xs text-amber-300">最老排队等待: {formatDuration(queueStats?.runtime?.queue?.queued_oldest_wait_seconds)}</div>
        </div>

        <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-2">
          <div className="text-xs text-gray-400">工作进程</div>
          <div className="text-2xl font-bold text-emerald-300">{queueStats?.runtime?.workers?.active_running_workers ?? 0}</div>
          <div className="text-xs text-gray-500">当前活跃 worker 数</div>
          <div className="text-xs text-gray-300">配置线程: {queueStats?.runtime?.workers?.configured_threads ?? 0}</div>
          <div className="text-xs text-gray-300">线程: {queueStats?.runtime?.workers?.effective_threads ?? 0} / 请求 {queueStats?.runtime?.workers?.requested_threads ?? 0}</div>
          <div className="text-xs text-cyan-300">进程位 已用/总量/可用: {queueStats?.runtime?.workers?.slots_in_use ?? 0} / {queueStats?.runtime?.workers?.slots_total ?? 0} / {queueStats?.runtime?.workers?.slots_available ?? 0}</div>
          {queueStats?.runtime?.workers?.restart_required_for_thread_change ? (
            <div className="text-xs text-amber-300">检测到线程配置已变化，需重启后端以应用</div>
          ) : (
            <div className="text-xs text-gray-500">线程配置与当前运行态一致</div>
          )}
          <div className="text-xs text-gray-300">心跳异常任务: {queueStats?.runtime?.workers?.stale_running_tasks ?? 0}</div>
          <div className="text-xs text-amber-300">最久运行: {formatDuration(queueStats?.runtime?.workers?.oldest_running_seconds)}</div>
        </div>

        <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-2">
          <div className="text-xs text-gray-400">回调队列</div>
          <div className="text-2xl font-bold text-cyan-300">{queueStats?.callback?.pending_jobs ?? 0}</div>
          <div className="text-xs text-gray-500">待回调/待落库任务</div>
          <div className="text-xs text-cyan-300">回调并发位 已用/总量/可用: {queueStats?.callback?.slots_in_use ?? 0} / {queueStats?.callback?.slots_total ?? 0} / {queueStats?.callback?.slots_available ?? 0}</div>
          <div className="text-xs text-gray-300">回调缓存: {queueStats?.callback?.store_count ?? 0}</div>
          <div className="text-xs text-gray-300">Async Inflight: {queueStats?.callback?.async_inflight ?? 0}</div>
          <div className="text-xs text-gray-300">Persist Inflight(I/V): {queueStats?.callback?.image_persist_inflight ?? 0} / {queueStats?.callback?.video_persist_inflight ?? 0}</div>
          <div className="text-xs text-gray-300">回调并发: {queueStats?.callback?.effective_threads ?? 0} / 请求 {queueStats?.callback?.requested_threads ?? 0}</div>
        </div>

        <div className="bg-[#111114] rounded-xl border border-white/10 p-4 space-y-2">
          <div className="text-xs text-gray-400">轮询与回调失败补偿</div>
          <div className="text-2xl font-bold text-orange-300">{queueStats?.callback_loss_retry?.retrying_jobs ?? 0}</div>
          <div className="text-xs text-gray-500">补偿重试中的任务</div>
          <div className="text-xs text-cyan-300">补偿工作位 已用/总量/可用: {queueStats?.callback_loss_retry?.worker_slots_in_use ?? 0} / {queueStats?.callback_loss_retry?.worker_slots_total ?? 0} / {queueStats?.callback_loss_retry?.worker_slots_available ?? 0}</div>
          <div className="text-xs text-cyan-300">补偿扫描批次 已用/总量/可用: {queueStats?.callback_loss_retry?.scan_batch_in_use ?? 0} / {queueStats?.callback_loss_retry?.scan_batch_size ?? 0} / {queueStats?.callback_loss_retry?.scan_batch_available ?? 0}</div>
          <div className="text-xs text-gray-300">轮询模式活跃任务: {queueStats?.polling?.active_polling_like_jobs ?? 0}</div>
          <div className="text-xs text-gray-300">纯回调模式生效: {queueStats?.polling?.pure_callback_mode_effective ? '是' : '否'}</div>
          <div className="text-xs text-gray-300">启动模式: {queueStats?.polling?.startup_mode || '-'}</div>
          <div className="text-xs text-gray-300">自动模式配置: {queueStats?.polling?.pure_callback_mode_auto ? '开' : '关'} | 手动模式配置: {queueStats?.polling?.pure_callback_mode_manual ? '开' : '关'}</div>
          <div className="text-xs text-gray-300">启动环境判定(public deploy): {queueStats?.polling?.startup_public_deploy_detected ? '是' : '否'}</div>
          <div className="text-xs text-gray-300">超时失败任务: {queueStats?.callback_loss_retry?.timeout_failed_jobs ?? 0}</div>
          <div className="text-xs text-gray-300">补偿候选任务: {queueStats?.callback_loss_retry?.compensation_candidate_jobs ?? 0}</div>
          <div className="text-xs text-gray-300">补偿线程: {queueStats?.callback_loss_retry?.worker_started ? '运行中' : '未启动'}</div>
        </div>
      </div>

      <div className="bg-[#111114] p-5 rounded-xl border border-white/10">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">Global Thread Config</h3>
        <div className="flex items-end gap-6 flex-wrap">
          <div className="space-y-1 flex-1 max-w-[200px]">
            <label className="text-sm text-gray-400">Queue Worker Threads</label>
            <input type="number" min="1" value={config.queue_threads} onChange={e => setConfig({...config, queue_threads: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
            <div className="text-xs text-gray-500">Default: 10</div>
          </div>
          <div className="space-y-1 flex-1 max-w-[200px]">
            <label className="text-sm text-gray-400">Callback Threads</label>
            <input type="number" min="1" value={config.callback_threads} onChange={e => setConfig({...config, callback_threads: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
            <div className="text-xs text-gray-500">Default: 10</div>
          </div>
          <div className="space-y-1 flex-1 min-w-[260px]">
            <label className="text-sm text-gray-400 block">Video Completion Mode</label>
            <label className="inline-flex items-center gap-2 text-sm text-gray-200 mb-1">
              <input type="checkbox" checked={Boolean(config.pure_callback_mode_auto)} onChange={e => setConfig({...config, pure_callback_mode_auto: e.target.checked})} />
              Auto switch by runtime (public deploy on, local off)
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-gray-200">
              <input type="checkbox" disabled={Boolean(config.pure_callback_mode_auto)} checked={Boolean(config.pure_callback_mode)} onChange={e => setConfig({...config, pure_callback_mode: e.target.checked})} />
              Pure Callback Mode (submit then wait callback)
            </label>
            <div className="mt-2 flex items-center gap-2 text-xs">
              <span className={`px-2 py-0.5 rounded-full border ${pureCallbackRuntime.effective ? 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10' : 'text-amber-300 border-amber-500/40 bg-amber-500/10'}`}>
                {pureCallbackRuntime.text}
              </span>
              <span className="text-gray-400">来源: {pureCallbackRuntime.source}</span>
            </div>
            <div className="text-xs text-gray-500">Auto enabled: deploy env uses pure callback, local keeps original polling mode.</div>
          </div>
          <div className="space-y-1 flex-1 min-w-[260px]">
            <label className="text-sm text-gray-400 block">Callback Loss Retry</label>
            <label className="inline-flex items-center gap-2 text-sm text-gray-200">
              <input type="checkbox" checked={Boolean(config.callback_loss_retry_enabled)} onChange={e => setConfig({...config, callback_loss_retry_enabled: e.target.checked})} />
              Requeue stale jobs when callback missing
            </label>
            <div className="text-xs text-gray-500">Retry submit when callback not received in time.</div>
          </div>
          <div className="space-y-1 flex-1 max-w-[220px]">
            <label className="text-sm text-gray-400">Retry After Seconds</label>
            <input type="number" min="60" value={config.callback_loss_retry_after_seconds} onChange={e => setConfig({...config, callback_loss_retry_after_seconds: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div className="space-y-1 flex-1 max-w-[220px]">
            <label className="text-sm text-gray-400">Max Submit Retries</label>
            <input type="number" min="0" max="5" value={config.callback_loss_max_submit_retries} onChange={e => setConfig({...config, callback_loss_max_submit_retries: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div className="space-y-1 flex-1 min-w-[260px]">
            <label className="text-sm text-gray-400 block">Compensation Scan</label>
            <label className="inline-flex items-center gap-2 text-sm text-gray-200">
              <input type="checkbox" checked={Boolean(config.callback_compensation_scan_enabled)} onChange={e => setConfig({...config, callback_compensation_scan_enabled: e.target.checked})} />
              Enable periodic callback reconciliation
            </label>
            <div className="text-xs text-gray-500">Scan running jobs and reconcile callback states.</div>
          </div>
          <div className="space-y-1 flex-1 max-w-[220px]">
            <label className="text-sm text-gray-400">Scan Interval Seconds</label>
            <input type="number" min="10" value={config.callback_compensation_scan_interval_seconds} onChange={e => setConfig({...config, callback_compensation_scan_interval_seconds: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div className="space-y-1 flex-1 max-w-[220px]">
            <label className="text-sm text-gray-400">Scan Batch Size</label>
            <input type="number" min="1" max="200" value={config.callback_compensation_scan_batch_size} onChange={e => setConfig({...config, callback_compensation_scan_batch_size: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <button onClick={handleSaveConfig} disabled={savingConfig} className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded font-medium transition-colors">
            {savingConfig ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Save & Apply
          </button>
        </div>
      </div>

      <div className="bg-[#111114] rounded-xl border border-white/10 overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="bg-white/5 border-b border-white/10">
            <tr>
              <th className="p-4 font-medium">Task Info</th>
              <th className="p-4 font-medium">Status & Error</th>
              <th className="p-4 font-medium">Timing & Details</th>
              <th className="p-4 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {tasks.length === 0 ? (
              <tr><td colSpan="4" className="p-8 text-center text-gray-500">No tasks in queue.</td></tr>
            ) : tasks.map(task => {
              const payload = task.payload || {};
              const prompt = payload.prompt || payload.video_prompt || payload.image_prompt || '';
              const diag = task.callback_diag || {};
              return (
              <tr key={task.job_id} onClick={() => setSelectedTask(task)} className="hover:bg-white/5 transition-colors cursor-pointer">
                <td className="p-4 max-w-[200px] align-top">
                  <div className="font-bold text-sm text-white">{task.kind}</div>
                  <div className="text-[11px] text-gray-500 font-mono mt-1" title={task.job_id}>{(task.job_id || '').slice(0, 12)}...</div>
                  <div className="text-xs text-blue-400 mt-1">User: {task.user_id}</div>
                  {prompt && <div className="text-xs text-gray-500 mt-2 line-clamp-2 truncate" title={prompt}>Prompt: {prompt}</div>}
                </td>
                <td className="p-4 max-w-[300px] align-top">
                  <span className={"inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium "}>
                    {task.status === 'queued' ? <Clock size={14} /> :
                     (task.status === 'processing' || task.status === 'running') ? <Loader2 size={14} className="animate-spin" /> :
                     <PlayCircle size={14} />}
                    {(task.status || '').toUpperCase()}
                  </span>
                  {diag.upstream_submit_state && (
                    <div className="mt-2 text-[11px] text-cyan-300">
                      Upstream: {diag.upstream_submit_state}
                    </div>
                  )}
                  {Number(diag.callback_submit_retries || 0) > 0 && (
                    <div className="mt-1 text-[11px] text-amber-300">
                      Callback retry: {Number(diag.callback_submit_retries || 0)}
                    </div>
                  )}
                  {diag.provider_task_id && (
                    <div className="mt-1 text-[11px] text-gray-400 truncate" title={diag.provider_task_id}>
                      Provider task: {String(diag.provider_task_id).slice(0, 24)}...
                    </div>
                  )}
                  {task.error && (
                    <div className="mt-2 text-xs text-red-400 overflow-hidden text-ellipsis" style={{display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical'}} title={task.error}>
                      <span className="font-bold text-red-500">Error:</span> {task.error}
                    </div>
                  )}
                  {task.worker_id && <div className="mt-1 text-[11px] text-gray-500 truncate" title={task.worker_id}>Worker: {task.worker_id}</div>}
                </td>
                <td className="p-4 text-xs text-gray-400 space-y-1 align-top">
                    <div><span className="text-gray-500">Created:</span> {task.created_at ? new Date(task.created_at * 1000).toLocaleString() : '-'}</div>
                    {task.started_at && <div><span className="text-gray-500">Started:</span> {new Date(task.started_at * 1000).toLocaleString()}</div>}
                  {task.finished_at && <div><span className="text-gray-500">Finished:</span> {new Date(task.finished_at * 1000).toLocaleString()}</div>}
                  {task.attempt_count > 0 && <div><span className="text-gray-500">Attempts:</span> {task.attempt_count}</div>}
                </td>
                <td className="p-4 text-right align-top">
                  {(task.status === 'queued' || task.status === 'running' || task.status === 'processing') && (
                    <button onClick={(e) => { e.stopPropagation(); handleCancel(task.job_id); }} className="p-2 text-gray-500 hover:text-red-400 bg-white/5 rounded-lg transition-colors" title="Cancel Task"> 
                      <Trash2 size={16} />
                    </button>
                  )}
                </td>
              </tr>
            )})}
          </tbody>
        </table>
      </div>

      {selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto" onClick={() => setSelectedTask(null)}>
          <div className="bg-[#1c1c21] rounded-xl border border-white/10 w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl relative" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-5 border-b border-white/10 shrink-0 sticky top-0 bg-[#1c1c21] z-10">
              <div>
                <h3 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-400">Task Details</h3>
                <div className="text-xs text-gray-500 mt-1">{selectedTask.job_id}</div>
              </div>
              <button onClick={() => setSelectedTask(null)} className="p-2 text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
                <X size={20} />
              </button>
            </div>
            
            <div className="p-5 overflow-y-auto min-h-0 space-y-6 flex-1">
              {/* Core Information */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-black/20 p-3 rounded-lg border border-white/5">
                  <div className="text-xs text-gray-500 mb-1 font-medium">Kind</div>
                  <div className="text-sm font-semibold text-blue-300">{selectedTask.kind}</div>
                </div>
                <div className="bg-black/20 p-3 rounded-lg border border-white/5">
                  <div className="text-xs text-gray-500 mb-1 font-medium">Status</div>
                  <div className="text-sm font-semibold capitalize text-green-300">{selectedTask.status}</div>
                </div>
                <div className="bg-black/20 p-3 rounded-lg border border-white/5">
                  <div className="text-xs text-gray-500 mb-1 font-medium">User ID</div>
                  <div className="text-sm font-semibold text-purple-300">{selectedTask.user_id}</div>
                </div>
                <div className="bg-black/20 p-3 rounded-lg border border-white/5">
                  <div className="text-xs text-gray-500 mb-1 font-medium">Attempt</div>
                  <div className="text-sm font-semibold text-orange-300">{selectedTask.attempt_count}</div>
                </div>
                {(selectedTask.payload?.system_api_id || selectedTask.payload?.function_name) && (
                  <div className="col-span-2 lg:col-span-4 bg-black/20 p-3 rounded-lg border border-white/5">
                    <div className="text-xs text-gray-500 mb-1 font-medium">API Called</div>
                    <div className="text-sm font-semibold text-pink-300">
                      {getApiName(selectedTask.payload?.system_api_id) || selectedTask.payload?.function_name || 'Unknown'}
                      {selectedTask.payload?.function_name && <span className="ml-2 text-xs text-gray-500 font-normal opacity-70">({selectedTask.payload.function_name})</span>}
                    </div>
                  </div>
                )}
              </div>

              {/* Callback Compensation Diagnostics */}
              {!!selectedTask?.callback_diag && (
                <div className="bg-black/20 p-4 rounded-lg border border-white/5 space-y-2">
                  <div className="text-sm font-semibold text-cyan-300">Callback Diagnostics</div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-2 text-xs text-gray-300">
                    <div><span className="text-gray-500">Job Status:</span> {selectedTask.callback_diag.job_status || '-'}</div>
                    <div><span className="text-gray-500">Upstream Submit State:</span> {selectedTask.callback_diag.upstream_submit_state || '-'}</div>
                    <div><span className="text-gray-500">Provider Task ID:</span> {selectedTask.callback_diag.provider_task_id || '-'}</div>
                    <div><span className="text-gray-500">Callback Ticket:</span> {selectedTask.callback_diag.provider_callback_ticket || '-'}</div>
                    <div><span className="text-gray-500">Callback Submit Retries:</span> {Number(selectedTask.callback_diag.callback_submit_retries || 0)}</div>
                    <div><span className="text-gray-500">Callback Retry At:</span> {selectedTask.callback_diag.callback_retry_at || '-'}</div>
                    <div><span className="text-gray-500">Started At:</span> {selectedTask.callback_diag.started_at || '-'}</div>
                    <div><span className="text-gray-500">Finished At:</span> {selectedTask.callback_diag.finished_at || '-'}</div>
                  </div>
                  {selectedTask.callback_diag.error && (
                    <div className="text-xs text-red-300"><span className="text-red-500 font-semibold">Diag Error:</span> {selectedTask.callback_diag.error}</div>
                  )}
                </div>
              )}

              {/* Timestamps */}
              <div className="bg-black/20 p-4 rounded-lg border border-white/5 space-y-3">
                <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                  <Clock size={16} className="text-gray-400" /> Timestamps
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500 mr-2">Created:</span>
                    <span className="text-gray-200">{selectedTask.created_at ? new Date(selectedTask.created_at * 1000).toLocaleString() : '-'}</span>
                  </div>
                  {selectedTask.started_at && (
                    <div>
                      <span className="text-gray-500 mr-2">Started:</span>
                      <span className="text-gray-200">{new Date(selectedTask.started_at * 1000).toLocaleString()}</span>
                    </div>
                  )}
                  {selectedTask.finished_at && (
                    <div>
                      <span className="text-gray-500 mr-2">Finished:</span>
                      <span className="text-gray-200">{new Date(selectedTask.finished_at * 1000).toLocaleString()}</span>
                    </div>
                  )}
                </div>
                {selectedTask.worker_id && (
                  <div className="pt-2 mt-2 border-t border-white/5">
                    <span className="text-gray-500 mr-2 text-sm">Worker ID:</span>
                    <span className="text-gray-300 font-mono text-xs">{selectedTask.worker_id}</span>
                  </div>
                )}
              </div>

              {/* Error Message */}
              {selectedTask.error && (
                <div className="bg-red-500/10 p-4 rounded-lg border border-red-500/20">
                  <h4 className="text-sm font-semibold text-red-400 mb-2 flex items-center gap-2">
                     Error Log
                  </h4>
                  <pre className="text-red-300 text-xs whitespace-pre-wrap font-mono">
                    {selectedTask.error}
                  </pre>
                </div>
              )}

              {/* Full Payload */}
              <div className="bg-black/40 p-4 rounded-lg border border-white/5">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-emerald-400">Combined Payload</h4>
                </div>
                <div className="relative">
                  <pre className="text-gray-300 text-xs whitespace-pre-wrap font-mono bg-[#111114] p-4 rounded border border-white/5 overflow-x-auto selection:bg-blue-500/30">
                    {JSON.stringify(
                      Object.fromEntries(
                        Object.entries(selectedTask.payload || {}).filter(([_, v]) => v !== null && v !== undefined && v !== '')
                      ), 
                      null, 2
                    )}
                  </pre>
                </div>
              </div>
            </div>
            
            <div className="p-4 border-t border-white/10 shrink-0 sticky bottom-0 bg-[#1c1c21] flex justify-end">
               <button onClick={() => setSelectedTask(null)} className="px-5 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors font-medium">
                 Close
               </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

