import sys

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

st1 = '    const SUBJECT_BATCH_RUNTIME_STALE_MS = 1000 * 60 * 5;'
st2 = '    const [historyList, setHistoryList] = useState([]);\n    const [showHistoryModal, setShowHistoryModal] = useState(false);\n    const [historyLoading, setHistoryLoading] = useState(false);\n'
if 'setHistoryList' not in content:
    content = content.replace(st1, st1 + '\n' + st2)

mth = '''    const handleLoadHistory = async (entityId) => {
        if (!getEntityHistory) return;
        setHistoryLoading(true);
        setShowHistoryModal(true);
        try {
            const data = await getEntityHistory(entityId);
            setHistoryList(data || []);
        } catch (e) {
            console.error('Failed to load history', e);
        } finally {
            setHistoryLoading(false);
        }
    };

    const handleRestoreHistory = async (historyId) => {
        if (!restoreEntityHistory || !viewingEntity) return;
        if (!confirm(t('Restore?', 'Are you sure you want to restore?'))) return;
        try {
            const result = await restoreEntityHistory(historyId);
            setViewingEntity(result);
            setEntities(prev => prev.map(e => e.id === result.id ? result : e));
            setShowHistoryModal(false);
            alert(t('Restored successfully!', 'Restored successfully!'));
        } catch (e) {
            console.error('Failed to restore history', e);
            alert('Failed to restore: ' + e.message);
        }
    };

    const handleSyncFromOld = async (entityId, sourceId) => {
        if (!syncEntityFromOld) return;
        try {
            const result = await syncEntityFromOld(entityId, sourceId);
            setViewingEntity(result);
            setEntities(prev => prev.map(e => e.id === result.id ? result : e));
            alert(t('Synced successfully!', 'Synced successfully!'));
        } catch (e) {
            console.error('Failed to sync', e);
            alert('Failed to sync: ' + e.message);
        }
    };
'''

if 'handleLoadHistory' not in content:
    content = content.replace('    // Delete Entity', mth + '\n    // Delete Entity')

ui = '''                                      {/* Sync & History Options */}
                                      <div className="pt-4 border-t border-white/10 flex items-center justify-between">
                                          {viewingEntity.existing_id ? (
                                              <button 
                                                  onClick={() => handleSyncFromOld(viewingEntity.id, viewingEntity.existing_id)}
                                                  className="px-3 py-1.5 text-xs font-medium bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 rounded border border-blue-500/30 transition-colors"
                                              >
                                                  {t('Sync from Source Entity', 'Sync from Source Entity')}
                                              </button>
                                          ) : (
                                              <div></div>
                                          )}
                                          <button 
                                              onClick={() => handleLoadHistory(viewingEntity.id)}
                                              className="px-3 py-1.5 text-xs font-medium bg-white/5 text-white/70 hover:bg-white/10 hover:text-white rounded border border-white/10 transition-colors"
                                          >
                                              {t('View History', 'View History')}
                                          </button>
                                      </div>
'''
if 'handleSyncFromOld' not in content:
    content = content.replace('                                      {/* Environment Details */}', ui + '\n                                      {/* Environment Details */}')

mod = '''
            {/* History Modal */}
            {showHistoryModal && (
                <div className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="bg-[#1a1b1e] rounded-xl border border-white/10 w-full max-w-lg flex flex-col max-h-[80vh] overflow-hidden shadow-2xl">
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-[#25262b]">
                            <h3 className="font-bold text-white flex items-center gap-2">
                                <History size={16} className="text-primary" />
                                {t('Entity History', 'Entity History')}
                            </h3>
                            <button onClick={() => setShowHistoryModal(false)} className="text-white/50 hover:text-white/90 transition-colors bg-white/5 hover:bg-white/10 p-1.5 rounded">
                                <X size={16} />
                            </button>
                        </div>
                        <div className="p-4 overflow-y-auto w-full">
                            {historyLoading ? (
                                <div className="py-8 flex justify-center"><Loader2 className="animate-spin text-white/50" /></div>
                            ) : historyList.length === 0 ? (
                                <div className="py-8 text-center text-white/40 text-sm">
                                    {t('No history records found.', 'No history records found.')}
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {historyList.map(h => (
                                        <div key={h.id} className="p-3 bg-white/5 rounded-lg border border-white/10 flex items-center justify-between">
                                            <div className="text-xs text-white/70">
                                                <div className="font-medium text-white mb-0.5">{h.remark || t('Snapshot', 'Snapshot')}</div>
                                                <div>{h.created_at ? new Date(h.created_at).toLocaleString() : ''}</div>
                                            </div>
                                            <button 
                                                onClick={() => handleRestoreHistory(h.id)}
                                                className="px-2.5 py-1 bg-primary text-white text-xs font-semibold rounded hover:bg-primary/90"
                                            >
                                                {t('Restore', 'Restore')}
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
'''
if 'History Modal' not in content:
    content = content.replace('        </>', mod + '\n        </>')

if 'History' not in content.split('lucide-react')[0]:
    content = content.replace('import { Search, Plus, Upload, X, Trash2, Edit3, Image as ImageIcon, Video, Box, FileText, Check, Loader2, Sparkles, Filter, ChevronDown, CheckCircle2, AlertCircle, RefreshCw, Layers } from \'lucide-react\';', 
                              'import { Search, Plus, Upload, X, Trash2, Edit3, Image as ImageIcon, Video, Box, FileText, Check, Loader2, Sparkles, Filter, ChevronDown, CheckCircle2, AlertCircle, RefreshCw, Layers, History } from \'lucide-react\';')

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to SubjectLibrary.jsx successfully!")
