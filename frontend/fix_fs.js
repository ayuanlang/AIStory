const fs = require('fs');
const p = 'c:/AS/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx';
let content = fs.readFileSync(p, 'utf8');

const replacement =             {/* History Modal */}
            {showHistoryModal && (
                <div className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="bg-[#1a1b1e] rounded-xl border border-white/10 w-full max-w-lg flex flex-col max-h-[80vh] overflow-hidden shadow-2xl">
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-[#25262b]">
                            <h3 className="font-bold text-white flex items-center gap-2">
                                <History size={16} className="text-primary" />
                                {t('实体历史', 'Entity History')}
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
                                    {t('暂无历史记录。', 'No history records found.')}
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {historyList.map(h => (
                                        <div key={h.id} className="p-3 bg-white/5 rounded-lg border border-white/10 flex items-center justify-between">
                                            <div className="text-xs text-white/70">
                                                <div className="font-medium text-white mb-0.5">{h.remark || t('普通快照', 'Snapshot')}</div>
                                                <div>{h.created_at ? new Date(h.created_at).toLocaleString() : ''}</div>
                                            </div>
                                            <button 
                                                onClick={() => handleRestoreHistory(h.id)}
                                                className="px-2.5 py-1 bg-primary text-white text-xs font-semibold rounded hover:bg-primary/90"
                                            >
                                                {t('恢复到此版本', 'Restore')}
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

;

content = content.replace('    </>\r\n    );\r\n};', replacement).replace('    </>\n    );\n};', replacement);
fs.writeFileSync(p, content);
console.log('Fixed file');
