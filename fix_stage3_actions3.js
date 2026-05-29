const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let text = fs.readFileSync(filePath, 'utf-8');

const sIdx = text.indexOf("key: `reimport-stage3-${cat.key}`");
console.log('sIdx', sIdx);
if (sIdx > -1) {
    const actionsStart = text.lastIndexOf("actions: [", sIdx);
    const actionsEnd = text.indexOf("],", sIdx) + 2;
    console.log(actionsStart, actionsEnd);
    
    if (actionsStart > -1 && actionsEnd > -1) {
        const replaceStr = `actions: [
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
        text = text.substring(0, actionsStart) + replaceStr + text.substring(actionsEnd);
        fs.writeFileSync(filePath, text, 'utf-8');
        console.log('Replaced successfully');
    }
}
