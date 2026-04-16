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
      setTasks(res.items || []);
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
              <th className="p-4 font-medium">Job ID / Type</th>
              <th className="p-4 font-medium">Status</th>
              <th className="p-4 font-medium">Created / Updated</th>
              <th className="p-4 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {tasks.length === 0 ? (
              <tr><td colSpan="4" className="p-8 text-center text-gray-500">No tasks in queue.</td></tr>
            ) : tasks.map(task => (
              <tr key={task.id} className="hover:bg-white/5 transition-colors">
                <td className="p-4">
                  <div className="font-medium">{task.task_type}</div>
                  <div className="text-xs text-gray-500 mt-1">{task.id.slice(0, 8)}...</div>
                </td>
                <td className="p-4">
                  <span className={"inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium "}>
                    {task.status === 'queued' ? <Clock size={14} /> :
                     task.status === 'processing' ? <Loader2 size={14} className="animate-spin" /> :
                     <PlayCircle size={14} />}
                    {task.status.toUpperCase()}
                  </span>
                </td>
                <td className="p-4 text-gray-400">
                  <div>{new Date(task.created_at).toLocaleString()}</div>
                </td>
                <td className="p-4 text-right">
                  {(task.status === 'queued' || task.status === 'processing') && (
                    <button onClick={() => handleCancel(task.id)} className="p-2 text-gray-500 hover:text-red-400 bg-white/5 rounded-lg transition-colors">
                      <Trash2 size={16} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

