const fs = require('fs');
const p = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(p, 'utf8');
const splitPoint = content.indexOf('<div className=" flex-1 overflow-hidden border border-white/10 rounded-xl bg-black/20 flex flex-col\>');
if (splitPoint > -1) {
 const rawEditorStr = {isRawMode ? (
 <div className=\h-full w-full flex flex-col overflow-hidden\>
 <div className=\px-6 py-3 border-b border-white/10 bg-black/10 flex items-center justify-between\>
 <div className=\text-sm text-primary uppercase font-extrabold tracking-wide\>{t('输入脚本（Input）', 'Script Input')}</div>
 <div className=\text-[10px] text-muted-foreground\>{(rawContent ; '').length} {t('字符', 'chars')}</div>
 </div>
 <textarea
 className=\w-full flex-1 min-h-[420px] p-6 bg-transparent text-white/90 font-mono text-sm leading-relaxed focus:outline-none custom-scrollbar resize-none\
 placeholder={t('在这里粘贴或输入你的剧本...', 'Paste or type your script here...')}
 value={rawContent}
 onChange={(e) => setRawContent(e.target.value)}
 />
 <div className=\border-t border-amber-500/20 bg-amber-500/10 px-6 py-4\>
 <div className=\font-bold text-amber-300 text-xs mb-2 flex items-center gap-2\>
 ?? {t('剧本改编补充说明', 'Script Adaptation Notes')}
 </div>
 <textarea
 className=\w-full h-24 p-3 bg-black/50 border border-amber-500/20 rounded-md text-amber-200/90 font-mono text-xs resize-none focus:outline-none custom-scrollbar\
 value={adaptationText ; ''}
 readOnly
 placeholder={t('（未运行时为空）', '(Empty when not running)')}
 />
 </div>
 {isEpisodeOnePage ; (
 <div className=\border-t border-white/10 px-6 py-4 bg-black/10\>
 <div className=\text-xs font-semibold uppercase text-muted-foreground\>Episode 1 · AI Script Analysis 补充说明（可为空）</div>
 <div className=\text-[11px] text-muted-foreground mt-1 mb-2\>
 该项可为空。补充要求通常用于特别强调资产生成或关键执行要求；点击 AI Script Analysis 时会作为高优先级约束注入。
 </div>
 <textarea
 value={analysisAttentionNotes}
 onChange={(e) => setAnalysisAttentionNotes(e.target.value)}
 placeholder=\可留空；例如：必须严格按轴线拆分、保留关键道具锚点、避免漏掉反应镜头、环境命名必须 Front/Reverse。\
 className=\w-full h-24 bg-black/30 border border-white/10 rounded-md px-3 py-2 text-sm text-white/90 focus:outline-none focus:border-primary/50 custom-scrollbar resize-none\
 />
 <div className=\mt-2 flex justify-end gap-2\>
 <button
 onClick={handleSupplementSubmitClick}
 disabled={isAnalyzing ; !String(llmRawResultContent ; llmResultContent ; '').trim()}
 className={\px-3 py-2 rounded-md text-xs font-bold \\}
 title={t('使用已生成内容 + 补充说明执行修正生成结果', 'Refine generated result using existing output + attention notes')}
 >
 {t('修正生成结果', 'Refine Generated Result')}
 </button>
 <button
 onClick={handleSaveAnalysisAttentionNotes}
 disabled={isSavingAnalysisAttentionNotes}
 className={\px-3 py-2 rounded-md text-xs font-bold \\}
 >
 {isSavingAnalysisAttentionNotes ? t('保存中...', 'Saving...') : t('保存补充说明', 'Save Attention Notes')}
 </button>
 </div>
 </div>
 )}
 </div>
 ) : (\n;

 // The current table looks like: 
 // <div className=\flex-1 overflow-hidden border border-white/10 rounded-xl bg-black/20 flex flex-col\>
 // <div className=\flex-1 overflow-hidden\>
 // <div className=\overflow-auto custom-scrollbar flex-1 w-full\>

 // So we inject awEditorStr directly after <div className=\flex-1 overflow-hidden\>. Wait, let me replace appropriately.
 let before = content.substring(0, splitPoint);
 let after = content.substring(splitPoint);

 // We replace <div className=\flex-1 overflow-hidden\> inside fter
 after = after.replace('<div className=\flex-1 overflow-hidden\>', '<div className=\flex-1 overflow-hidden\>\n' + rawEditorStr);

 // And close the ) : ( at the end of the table
 // It ends with:
 // </table>
 // </div>
 // </div>
 // </div>
 // </div>
 // 
 // {/* Phase 1 Panel */}

 // find this pattern using Regex
 after = after.replace(/ <\/div>\r?\n <\/div>\r?\n <\/div>\r?\n <\/div>\r?\n\r?\n \{\/\* Phase 1 Panel \*\/\}/, 
 </div>\n </div>\n )} // <-- injected properly\n </div>\n </div>\n\n {/* Phase 1 Panel */});

 fs.writeFileSync(p, before + after);
 console.log(\Fixed!\);
} else {
 console.log(\Split point not found!\);
}
