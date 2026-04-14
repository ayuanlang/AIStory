const fs = require('fs');
const path = 'C:\\AIStory\\frontend\\src\\pages\\editor\\components\\ShotsView.jsx';
let content = fs.readFileSync(path, 'utf8');

const targetStr = `<div className="relative inline-flex items-center ml-2 border border-white/20 rounded overflow-hidden">
                             <button
                                onClick={handleManualRebindMediaSlots}
                                disabled={isManualRebindingMedia || isBatchGenerating || isStoppingShotBatch}
                                className={\`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 \${isManualRebindingMedia ? 'bg-white/20 text-white/80 cursor-wait' : 'bg-white/10 text-white hover:bg-white/20'}\`}
                                title={t('手动回填历史媒体关联（只补空槽位）', 'Manual historical media rebind (fills empty slots only)')}
                            >
                                {isManualRebindingMedia ? <Loader2 className="w-3 h-3 animate-spin"/> : <RefreshCw className="w-3 h-3"/>}
                                <span>{t('回填', 'Rebind')}</span>
                            </button>
                             <button
                                onClick={handleBatchGenerate}
                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                className={\`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 \${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}\`}
                                title={t('批量生成缺失的起始/结束帧', 'Batch Generate Missing Start/End Frames')}
                            >
                                {(isBatchGenerating || isShotBatchStarting) ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}       
                                <span>{(isBatchGenerating || isShotBatchStarting) ? t('批量执行中...', 'Running...') : t('补帧', 'Frames')}</span>
                            </button>
                            <button
                                onClick={handleBatchGenerateJointDiptych}       
                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                className={\`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 \${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}\`}
                                title={t('按镜头批量执行首尾联生', 'Batch Generate Joint Start/End Diptychs')}
                            >
                                {(isBatchGenerating || isShotBatchStarting) ? <Loader2 className="w-3 h-3 animate-spin"/> : <PanelsTopLeft className="w-3 h-3"/>}
                                <span>{(isBatchGenerating || isShotBatchStarting) ? t('批量执行中...', 'Running...') : t('首尾联生', 'Joint')}</span>
                            </button>
                            <button
                                onClick={handleBatchGenerateVideo}
                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                className={\`px-3 py-1.5 text-xs flex items-center gap-1 transition-all border-r border-white/10 \${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}\`}`;

const replacementStr = `<div className="relative inline-flex items-center ml-2 border border-white/20 rounded z-[900]">
                             <div className="relative flex items-stretch h-full bg-primary/10 border-r border-white/20 group">
                                <button
                                    onClick={handleBatchGenerate}
                                    disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                    className={\`px-3 py-1.5 text-xs flex items-center justify-center gap-1 transition-all h-full \${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'text-primary hover:bg-primary/20'}\`}
                                    title={t('先首帧后尾帧批量生成/补帧', 'Batch Generate Missing Start/End Frames')}
                                >
                                    {(isBatchGenerating || isShotBatchStarting) ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                    <span>{(isBatchGenerating || isShotBatchStarting) ? t('批量执行中...', 'Running...') : t('批量生成分镜', 'Batch Generate Shots')}</span>
                                </button>
                                <div 
                                    className={\`relative flex items-stretch h-full \${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 cursor-wait' : 'hover:bg-primary/20'}\`}
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
                                            <div className="w-44 bg-gray-900 border border-white/20 rounded shadow-xl overflow-hidden flex items-stretch flex-col cursor-auto">
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
                                onClick={handleBatchGenerateVideo}
                                disabled={isBatchGenerating || isShotBatchStarting || isStoppingShotBatch}
                                className={\`px-3 py-1.5 h-full text-xs flex items-center gap-1 transition-all border-r border-white/10 \${(isBatchGenerating || isShotBatchStarting) ? 'bg-primary/20 text-primary cursor-wait' : 'bg-primary/10 text-primary hover:bg-primary/20'}\`}`;

content = content.replace(targetStr, replacementStr);
fs.writeFileSync(path, content, 'utf8');
console.log("Replaced successfully!");
