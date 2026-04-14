import re

path = 'C:/AIStory/frontend/src/pages/editor/components/ShotsView.jsx'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

target = re.compile(r'<div className="relative inline-flex items-center ml-2 border border-white/20 rounded overflow-hidden">((?:(?!</div).|\n)*?)handleBatchGenerateVideo', re.DOTALL)

replacement = '''<div className="relative inline-flex items-center ml-2 border border-white/20 rounded z-[900]">
                             <div className="relative flex items-stretch h-full bg-primary/10 border-r border-white/20 group">
                                <button
                                    onClick={handleBatchGenerate}
                                    disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                    className={px-3 py-1.5 text-xs flex items-center justify-center gap-1 transition-all h-full }
                                    title={t('先首帧后尾帧批量生成/补帧', 'Batch Generate Missing Start/End Frames')}
                                >
                                    {(isBatchGenerating || isShotBatchStarting) ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                    <span>{(isBatchGenerating || isShotBatchStarting) ? t('批量执行中...', 'Running...') : t('批量生成分镜', 'Batch Generate Shots')}</span>
                                </button>
                                <div 
                                    className={elative flex items-stretch h-full }
                                    onMouseEnter={() => setShowBatchGenerateMenu(true)}
                                    onMouseLeave={() => setShowBatchGenerateMenu(false)}
                                >
                                    <button
                                        disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                        className="px-1.5 py-1.5 h-full flex items-center justify-center border-l border-white/10 disabled:opacity-50"
                                    >
                                        <ChevronDown className="w-3 h-3 text-primary" />
                                    </button>
                                    {showBatchGenerateMenu && !isBatchGenerating && !isShotBatchStarting && !isStoppingShotBatch && (
                                        <div className="absolute top-full right-0 pt-1 z-[999]">
                                            <div className="w-44 bg-gray-900 border border-white/20 rounded shadow-xl overflow-hidden flex flex-col cursor-auto">
                                                <button
                                                    onClick={() => { setShowBatchGenerateMenu(false); handleBatchGenerate(); }}
                                                    className="w-full text-left px-3 py-2 text-xs text-white hover:bg-white/10 flex items-center justify-between"
                                                >
                                                    <span>{t('先首帧后尾帧', 'Start then End')}</span>
                                                    <span className="text-[10px] text-muted-foreground ml-2">(默认)</span>
                                                </button>
                                                <div className="h-px bg-white/10 w-full" />
                                                <button
                                                    onClick={() => { setShowBatchGenerateMenu(false); handleBatchGenerateJointDiptych(); }}
                                                    className="w-full text-left px-3 py-2 text-xs text-white hover:bg-white/10 flex items-center gap-2"
                                                >
                                                    <PanelsTopLeft className="w-3 h-3 text-muted-foreground"/>
                                                    <span>{t('首尾联生', 'Joint Start/End')}</span>
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                            <button
                                onClick={handleBatchGenerateVideo'''

m = target.search(c)
if m:
    c = c[:m.start()] + replacement + c[m.end()-22:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print("Replaced!")
else:
    print("Match failed")
