import re
p = 'c:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
c = open(p, 'r', encoding='utf-8').read()

target = '''                    {analysisFlowStatus.message && (
                        <div className="mb-2 text-xs opacity-95">{analysisFlowStatus.message}</div>
                    )}'''

replacement = '''                    {analysisFlowStatus.message && (
                        <div className="mb-2 text-xs opacity-95 flex items-center justify-between">
                            <div>{analysisFlowStatus.message}</div>
                            {isAnalyzing && analysisFlowStatus.phase === 'analyzing' && llmRawResultContent && (
                                <div className="text-[11px] text-purple-300 font-bold bg-purple-500/20 px-2 py-1 rounded">
                                    {t('???????: ', 'Received streaming chars: ')} {llmRawResultContent.length}
                                </div>
                            )}
                        </div>
                    )}'''

c = c.replace(target, replacement)
open(p, 'w', encoding='utf-8').write(c)
print("Done")
