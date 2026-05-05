import sys
import re

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# The modal was injected before </>. We should extract the modal string, and replace it completely with nothing, then inject exactly ONE copy at the end of the file.

modal_pattern = re.compile(r'\s*\{\/\* History Modal \*\/\}.*?(?=\s*\{\/\*|\s*<\/>|\s*<\/div>|\s*<div)', re.DOTALL)
# Actually it's easier to just find the exact modal block and remove all.
# Let's see the string of the modal.
mod = '''
            {/* History Modal */}
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
'''

# The previous broken mod had garbled text or english text... Let's remove ANY string starting with {/* History Modal */} up to the closing )} of the modal.
cleaned = re.sub(r'\s*\{\/\* History Modal \*\/\}\s*\{showHistoryModal && \([\s\S]*?\}\)\s*\}', '', content)

# Now inject it back once right before the last closing tag of the component in SubjectLibrary.jsx.
# Usually it's at the end before returning. SubjectLibrary is a large component returning a fragment. We should insert it before         </> but only the very last one.

if 'return (' in cleaned:
    # A safe place is right before the final         </>\n    );\n}; or similar. Let's look for </>\n        </div> or whatever.
    parts = cleaned.rsplit('</>', 1)
    if len(parts) == 2:
        cleaned = parts[0] + mod + '\n        </>' + parts[1]

with open(r'c:\AS\AIStory\frontend\src\pages\editor\components\SubjectLibrary.jsx', 'w', encoding='utf-8') as f:
    f.write(cleaned)

print("Cleanup successful")
