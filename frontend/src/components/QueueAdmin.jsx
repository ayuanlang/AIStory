import React, { useState, useEffect } from 'react';
import { RefreshCw, Trash2, StopCircle, Clock, PlayCircle, Loader2 } from 'lucide-react';
import { getAdminQueueTasks, cancelAdminQueueTask, cancelAllQueuedAdminTasks } from '../services/api';
import { confirmUiMessage } from '../lib/uiMessage';

export default function QueueAdmin() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);

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

  useEffect(() => {
    fetchTasks();
    const timer = setInterval(fetchTasks, 30000);
    return () => clearInterval(timer);
  }, []);

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
    <div className="p-6 max-w-7xl mx-auto text-white">
      <div className="flex items-center justify-between mb-6">
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
              <tr key={task.job_id} className="hover:bg-white/5 transition-colors">
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
                    <button onClick={() => handleCancel(task.job_id)} className="p-2 text-gray-500 hover:text-red-400 bg-white/5 rounded-lg transition-colors" title="Cancel Task"> 
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
  );
}

