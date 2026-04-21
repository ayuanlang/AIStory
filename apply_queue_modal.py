import re

def main():
    with open('frontend/src/components/QueueAdmin.jsx', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Import X icon
    old_imports = '''import { RefreshCw, Trash2, StopCircle, Clock, PlayCircle, Loader2, Save } from 'lucide-react';'''
    new_imports = '''import { RefreshCw, Trash2, StopCircle, Clock, PlayCircle, Loader2, Save, X } from 'lucide-react';'''
    if 'X }' not in text:
        text = text.replace(old_imports, new_imports, 1)

    # 2. Add state
    old_state = '''  const [savingConfig, setSavingConfig] = useState(false);'''
    new_state = '''  const [savingConfig, setSavingConfig] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);'''
    if 'selectedTask' not in text:
        text = text.replace(old_state, new_state, 1)

    # 3. Add onClick to row
    old_row = '''<tr key={task.job_id} className="hover:bg-white/5 transition-colors">'''
    new_row = '''<tr key={task.job_id} onClick={() => setSelectedTask(task)} className="hover:bg-white/5 transition-colors cursor-pointer">'''
    if 'cursor-pointer' not in text:
        text = text.replace(old_row, new_row, 1)

    # 4. Add button propagation stop
    old_button = '''<button onClick={() => handleCancel(task.job_id)} className="p-2 text-gray-500 hover:text-red-400 bg-white/5 rounded-lg transition-colors" title="Cancel Task">'''
    new_button = '''<button onClick={(e) => { e.stopPropagation(); handleCancel(task.job_id); }} className="p-2 text-gray-500 hover:text-red-400 bg-white/5 rounded-lg transition-colors" title="Cancel Task">'''
    if 'e.stopPropagation' not in text:
        text = text.replace(old_button, new_button, 1)

    # 5. Add Modal before final closing div
    old_end = '''    </div>
  );
}'''
    new_end = '''    </div>

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
}'''
    if 'selectedTask && (' not in text:
        text = text.replace(old_end, new_end, 1)

    with open('frontend/src/components/QueueAdmin.jsx', 'w', encoding='utf-8') as f:
        f.write(text)

if __name__ == '__main__':
    main()