import re, sys
p = 'c:/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx'
c = open(p, 'r', encoding='utf-8').read()

target = '''<textarea
                                ref={(el) => {
                                    if (el && isAnalyzing) {
                                        el.scrollTop = el.scrollHeight;
                                    }
                                }}
                                className="w-full h-64 px-4 py-3 bg-black/40 text-white/80 font-mono text-[12px] leading-relaxed focus:outline-none custom-scrollbar resize-y border border-white/10 rounded-md"
                                value={llmRawResultContent}
                                readOnly
                            />'''

replacement = '''<div className="w-full px-4 py-3 bg-black/40 text-white/80 font-mono text-[12px] border border-white/10 rounded-md flex items-center justify-between">
                                <span>{t('正在接收流式数据...', 'Receiving streaming data...')}</span>
                                <span className="text-purple-400 font-bold">{llmRawResultContent.length} {t('字符', 'chars')}</span>
                            </div>'''

c = c.replace(target, replacement)
open(p, 'w', encoding='utf-8').write(c)
