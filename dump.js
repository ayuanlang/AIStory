{/* Start Frame */}
                                    <div className="space-y-2">
                                        <div className="space-y-2">
                                        <div className="flex min-h-[52px] items-start justify-between gap-2">
                                            <div className="text-[10px] uppercase font-bold text-muted-foreground flex items-center gap-2">
                                                {t('起始帧', 'Start Frame')}
                                            </div>
                                            <div className="flex flex-wrap items-center justify-end gap-1">
                                                <button
                                                    onClick={() => openAssetDetailModal('start')}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded"
                                                >
                                                    {t('详情', 'Detail')}
                                                </button>
                                                <button 
                                                    onClick={async () => {
                                                        if (isShotFrameActionLocked('start')) {
                                                            notifyShotFrameActionLocked('start');
                                                            return;
                                                        }
                                                        openMediaPicker(async (url) => {
                                                            const newData = { image_url: url };
                                                            setEditingShot(prev => ({...prev, ...newData}));
                                                            // Auto-save user selection to ensure it counts as "latest selected"
                                                            await onUpdateShot(editingShot.id, newData);
                                                            onLog?.('Start Frame Image set', 'success');
                                                        }, { shotId: editingShot.id, shotFrameType: 'start' });
                                                    }}
                                                    disabled={isShotFrameActionLocked('start')}
                                                    className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-0.5 rounded flex items-center gap-1 disabled:opacity-40 disabled:cursor-not-allowed"
                                                    title={isShotFrameActionLocked('start') ? t('起始帧任务运行中，不能更换图片', 'Start frame job is running; image changes are disabled') : t('设置起始帧图片', 'Set start frame image')}
                                                >
                                                    <ImageIcon className="w-3 h-3"/> {t('设置', 'Set')}
                                                </button>
                                                {currentGeneratingState.start && (
                                                    <button 
                                                        onClick={() => handleForceStopShotImage('start')}
                                                        className="text-[10px] px-2 py-0.5 rounded flex items-center gap-1 bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/30"
                                                        title={t('停止重试循环', 'Stop Retry Loop')}
                                                    >
                                                        <div className="w-2 h-2 bg-current rounded-[1px]" />
                                                        {t('停止', 'Stop')}
                                                    </button>
                                                )}
                                                <button 
                                                    onClick={() => generateAssetWithLang('start')} 
                                                    disabled={currentShotGenerating}
                                                    className={`text-[10px] px-2 py-0.5 rounded flex items-center gap-1 ${currentShotGenerating ? 'bg-sky-500/10 text-sky-300/50 cursor-wait' : 'bg-sky-500/20 text-sky-300 hover:bg-sky-500/30'}`}
                                                >
                                                    {currentShotGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Wand2 className="w-3 h-3"/>}
                                                    {currentShotGenerating ? t('生成中...', 'Generating...') : t('生成', 'Generate')}
                                                </button>
                                                <button
                                                    onClick={() => handleGenerateShotDiptychFrames(shotImageCfgValue)}
                                                    disabled={currentShotGenerating}
                                                    className={`text-[10px] px-2 py-0.5 rounded flex items-center gap-1 ${currentShotGenerating ? 'bg-violet-500/10 text-violet-200/40 cursor-wait' : 'bg-violet-500/20 text-violet-200 hover:bg-violet-500/30'}`}
                                                    title={t('把起始帧与结束帧提示词拼成两宫格生图后自动拆分回填', 'Generate a two-panel composite from the start/end prompts, then split and apply both frames automatically')}
                                                >
                                                    {currentShotGenerating ? <Loader2 className="w-3 h-3 animate-spin"/> : <Layers className="w-3 h-3"/>}
                                                    {currentShotGenerating ? t('联生中...', 'Joint...') : t('首尾联生', 'Joint')}
                                                </button>
                                            </div>
                                        </div>
                                        {currentGeneratingState.start && (
                                            <div className="rounded-lg border border-amber-400/40 bg-amber-500/12 px-3 py-2 text-[11px] text-amber-50 shadow-[0_0_0_1px_rgba(251,191,36,0.08)]">
                                                <div className="flex items-center gap-2 font-bold uppercase tracking-[0.12em] text-amber-100">
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                    {t('起始帧生成中', 'Start Frame In Progress')}
                                                </div>
                                                <div className="mt-1 text-amber-50/75">
                                                    {t('当前预览会在生成完成后自动刷新，替换与删除入口已锁定。', 'This preview will refresh automatically when generation completes. Replace and delete actions are locked.')}
                                                </div>
                                            </div>
                                        )}
                                        <div style={mediaAspectStyle} className={`bg-black rounded border relative group overflow-hidden cursor-pointer flex items-center justify-center transition-colors ${!isPortrait ? 'aspect-video' : ''} ${currentGeneratingState.start ? 'border-amber-400/60 shadow-[0_0_0_1px_rgba(251,191,36,0.12)]' : 'border-white/10'}`} onClick={() => openAssetDetailModal('start')}>
                                            {currentGeneratingState.start && (
                                                <div className="absolute inset-0 bg-black/68 z-10 flex items-center justify-center flex-col gap-3">
                                                    <div className="rounded-full border border-amber-300/30 bg-amber-500/10 p-3">
                                                        <Loader2 className="w-7 h-7 animate-spin text-amber-200"/>
                                                    </div>
                                                    <div className="px-6 text-center">
                                                        <div className="text-sm font-bold uppercase tracking-[0.16em] text-amber-100">{t('正在生成起始帧', 'Generating Start Frame')}</div>
                                                        <div className="mt-1 text-[11px] text-white/75">{t('生成完成后会自动更新这里的画面', 'The preview here will update automatically when generation completes')}</div>
                                                    </div>
                                                </div>
                                            )}
                                            {editingShot.image_url ? (
                                                <>
                                                    <SafeImage
                                                        src={editingShot.image_url}
                                                        className="max-w-full max-h-full object-contain cursor-pointer hover:opacity-90 transition-opacity" 
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            openAssetDetailModal('start');
                                                        }}
                                                        alt={t('起始帧', 'Start Frame')}
                                                    />
                                                    <button 
                                                        onClick={async (e) => {
                                                            e.stopPropagation();
                                                            if (isShotFrameActionLocked('start')) {
                                                                notifyShotFrameActionLocked('start');
                                                                return;
                                                            }
                                                            if(!await confirmUiMessage("Delete Start Frame image?")) return;
                                                            const newData = { image_url: "" };
                                                            await onUpdateShot(editingShot.id, newData);
                                                            setEditingShot(prev => ({...prev, ...newData}));
                                                            onLog?.('Start Frame Image removed', 'info');
                                                        }}
                                                        disabled={isShotFrameActionLocked('start')}
                                                        className="absolute top-2 right-2 p-1.5 bg-black/60 hover:bg-red-500/80 text-white rounded-md opacity-0 group-hover:opacity-100 transition-all z-20 disabled:opacity-40 disabled:cursor-not-allowed"
                                                        title={isShotFrameActionLocked('start') ? t('起始帧任务运行中，不能删除图片', 'Start frame job is running; image removal is disabled') : t('删除起始帧', 'Delete Start Frame')}
                                                    >
                                                        <Trash2 className="w-3 h-3"/>
                                                    </button>
                                                </>
                                            ) : (
                                                <div className="absolute inset-0 flex items-center justify-center opacity-20"><ImageIcon className="w-8 h-8"/></div>
                                            )}
                                        </div>
                                        <PromptMentionTextarea entities={entities} uiLang={uiLang}
                                            className="w-full bg-black/20 border border-white/10 rounded p-2 text-xs focus:border-primary/50 outline-none resize-none h-[60px]"
                                            placeholder={shotPromptDisplayLang === 'cn' ? t('起始帧提示词（中文）...', 'Start Frame Prompt (CN)...') : t('起始帧提示词...', 'Start Frame Prompt...')}
                                            value={shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.start_frame_cn || ''; } catch(e) { return ''; } })() : (editingShot.start_frame || '')}
                                            onChange={(e) => {
                                                const tech = JSON.parse(editingShot.technical_notes || '{}');
                                                tech.manual_start_frame = true;
                                                if (shotPromptDisplayLang === 'cn') {
                                                    tech.start_frame_cn = e.target.value;
                                                    setEditingShot({...editingShot, technical_notes: JSON.stringify(tech)});
                                                } else {
                                                    setEditingShot({...editingShot, start_frame: e.target.value, technical_notes: JSON.stringify(tech)});
                                                }
                                            }}
                                        />
                                        </div>
                                        <div>
                                        <ReferenceManager 
                                            shot={editingShot} 
                                            entities={entities} 
                                            onUpdate={(updates) => { persistEditingShotUpdates(updates); }} 
                                            title={t('参考图（起始帧）', 'Refs (Start)')}
                                            promptText={shotPromptDisplayLang === 'cn' ? (() => { try { return JSON.parse(editingShot.technical_notes || '{}')?.start_frame_cn || ''; } catch(e) { return ''; } })() : (editingShot.start_frame || '')}
                                            uiLang={uiLang}
                                            onPickMedia={openMediaPicker}
                                            storageKey="ref_image_urls"
                                            strictPromptOnly={true}
                                            onFindPrevFrame={() => {
                                                // Logic to find PREVIOUS shot end frame
                                                const idx = shots.findIndex(s => s.id === editingShot.id);
                                                if (idx > 0) {
                                                    try {
                                                        const prev = shots[idx-1];
                                                        const t = JSON.parse(prev.technical_notes || '{}');
                                                        const url = t.end_frame_url || prev.video_url || prev.image_url;
                                                        if (url) {
                                                            onLog?.("Found previous shot frame: " + prev.shot_id, "success");
                                                            return url;
                                                        } else {
                                                            onLog?.("Previous shot has no media.", "warning");
                                                            return null;
                                                        }
                                                    } catch(e) { return null; }
                                                } else {
                                                    onLog?.("This is the first shot.", "info");
                                                    return null;
                                                }
                                            }}
                                        />
                                        </div>
                                    </div>


                                    