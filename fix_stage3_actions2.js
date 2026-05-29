const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let text = fs.readFileSync(filePath, 'utf-8');

const regex = /actions:\s*\[\s*\{\s*key:\s*`reimport-stage3-\${cat\.key}`[\s\S]*?\}\s*\]/g;

text = text.replace(regex, `actions: [
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
                ]`);

fs.writeFileSync(filePath, text, 'utf-8');
console.log('done stage 3 actions fixed');