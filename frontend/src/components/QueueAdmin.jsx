import React, { useState, useEffect } from 'react';
import { RefreshCw, Trash2, StopCircle, Clock, PlayCircle, Loader2, Save, X } from 'lucide-react';
import { getAdminQueueTasks, cancelAdminQueueTask, cancelAllQueuedAdminTasks, getAdminQueueConfig, updateAdminQueueConfig } from '../services/api';
import { confirmUiMessage, notifyUiMessage } from '../lib/uiMessage';

export default function QueueAdmin() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState({ queue_threads: 20, callback_threads: 20 });
  const [savingConfig, setSavingConfig] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);

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

  useEffect(() => {
    fetchTasks();
    fetchConfig();
    const timer = setInterval(fetchTasks, 30000);
    return () => clearInterval(timer);
  }, []);

  const handleSaveConfig = async () => {
    setSavingConfig(true);
    try {
      await updateAdminQueueConfig({
        queue_threads: Number(config.queue_threads),
        callback_threads: Number(config.callback_threads)
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
          <button onClick={fetchTasks} className="flex items-center gap-2 px-4 py-2 bg-white/10 rounded-lg hover:bg-white/20 transition-colors">
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      <div className="bg-[#111114] p-5 rounded-xl border border-white/10">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">Global Thread Config</h3>
        <div className="flex items-end gap-6">
          <div className="space-y-1 flex-1 max-w-[200px]">
            <label className="text-sm text-gray-400">Queue Worker Threads</label>
            <input type="number" min="1" value={config.queue_threads} onChange={e => setConfig({...config, queue_threads: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
            <div className="text-xs text-gray-500">Default: 20</div>
          </div>
          <div className="space-y-1 flex-1 max-w-[200px]">
            <label className="text-sm text-gray-400">Callback Threads</label>
            <input type="number" min="1" value={config.callback_threads} onChange={e => setConfig({...config, callback_threads: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500" />
            <div className="text-xs text-gray-500">Default: 20</div>
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
              </div>

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
                    {JSON.stringify(selectedTask.payload || {}, null, 2)}
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

