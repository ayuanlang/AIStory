const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let text = fs.readFileSync(filePath, 'utf-8');

// Stage 1
text = text.replace(/badge: adaptedScript \? t\('可回填', 'Re-importable'\) : t\('待输出', 'Pending'\)/, "badge: adaptedScript ? t('展开可回填', 'Re-importable') : t('展开待输出', 'Pending')");
text = text.replace(/label: t\('回填剧本', 'Restore Script'\)/, "label: t('回填剧本重跑覆盖', 'Restore & Rerun')");
text = text.replace(/badge: visualBackfillJson \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/, "badge: visualBackfillJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");

// Stage 2
text = text.replace(/badge: sceneMarkdown \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/, "badge: sceneMarkdown ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");
text = text.replace(/label: t\('重新导入', 'Re-import'\)/g, "label: t('重新导入重跑覆盖', 'Re-import & Rerun')");
text = text.replace(/badge: subjectIndex \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/, "badge: subjectIndex ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");

// Stage 3
text = text.replace(/badge: assetDesignJson \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/, "badge: assetDesignJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");
text = text.replace(/label: t\('全部导入', 'Import All'\)/, "label: t('全部导入重跑全部', 'Import All & Rerun')");

// Stage 3 partials
text = text.replace(/badge: catJson \? t\('可导入', 'Importable'\) : t\('待输出', 'Pending'\)/g, "badge: catJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending')");
text = text.replace(/btnZh: '重跑 道具'/g, "btnZh: '局部导入重跑道具'");
text = text.replace(/btnZh: ' 重跑封面'/g, "btnZh: '局部导入重跑封面'");

// The regex for replacing the stage 3 partial buttons
const repl_stage3_partial = `                actions: [
                    {
                        key: \`reimport-stage3-\${cat.key}-and-rerun\`,
                        label: t(cat.btnZh, cat.btnEn),
                        icon: 'refresh',
                        onClick: async () => {
                            await handleImportStageArtifact({
                                content: catJson,
                                importType: 'json',
                                label: \`stage3 \${cat.key} json\`,
                                importOptions: {
                                    subjectsJson: catObj || null,
                                    suppressAlerts: false,
                                },
                            });
                            handleRetryPhase2({ targetEntityTypes: [cat.key] });
                        },
                        disabled: isAnalyzing || isRetryingPhase2 || !catJson || !getStageOutputContent('stage2', 'subject_index'),
                        loading: isRetryingPhase2 && (phase2RetryOptionsRef.current?.targetEntityTypes?.includes(cat.key)),
                    }
                ],`;

text = text.replace(/actions:\s*\[[\s\S]*?label:\s*t\('局部导入.*?'[\s\S]*?targetEntityTypes:\s*\[cat\.key\][\s\S]*?\}\,?\s*\]\,/g, repl_stage3_partial);

// Wait, the Stage 3 partial buttons in the HEAD version don't say `t('局部导入...` yet. They say `t(cat.btnZh...` or something. Let me check the code for stage 3 loop.
fs.writeFileSync(filePath, text, 'utf-8');
console.log('done texts 1');
