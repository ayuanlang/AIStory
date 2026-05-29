const fs = require('fs');
const filePath = 'c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(filePath, 'utf-8');

const badChunk = \`            cards.push({
                key: \\\\stage3-asset-\\\\\\\\,
                eyebrow: t('第三阶段局部', 'Stage 3 Partial'),
                title: t(cat.labelZh, cat.labelEn),
                status: catJson ? 'completed' : 'idle',
                badge: catJson ? t('可导入', 'Importable') : t('待输出', 'Pending'),
                summary: t(\\\\局部的\\\\结果。\\\\, \\\\Stage 3 \\\\ result.\\\\),
                content: formatArtifactContent(catJson, 'json'),
                actions: [
                    {
                        key: \\\\
eimport-stage3-\\\\\\\\,
                        label: t('局部导入', 'Import Partial'),
                        icon: 'refresh',
                        onClick: () => handleImportStageArtifact({
                            content: catJson,
                            importType: 'json',
                            label: \\\\stage3 \\\\ json\\\\,
                            importOptions: {
                                subjectsJson: catObj || null,
                                suppressAlerts: false,
                            },
                        }),
                        disabled: isAnalyzing || !catJson,
                        loading: false,
                    },
                    {
                        key: \\\\
estart-stage3-\\\\\\\\,
                        label: t(cat.btnZh, cat.btnEn),
                        icon: 'repeat',
                        onClick: () => handleRetryPhase2({ targetEntityTypes: [cat.key] }),
                        disabled: isAnalyzing || isRetryingPhase2 || !getStageOutputContent('stage2', 'subject_index'),
                        loading: isRetryingPhase2 && phase2RetryOptionsRef.current?.targetEntityTypes?.includes(cat.key),
                    }
                ],
                placeholder: t(\\\\尚未返回\\\\结果。\\\\, \\\\No \\\\ output yet.\\\\),
            });\`;

const goodChunk = \`            cards.push({
                key: \\\`stage3-asset-\${cat.key}\\\`,
                eyebrow: t('第三阶段局部', 'Stage 3 Partial'),
                title: t(cat.labelZh, cat.labelEn),
                status: catJson ? 'completed' : 'idle',
                badge: catJson ? t('展开可导入', 'Importable') : t('展开待输出', 'Pending'),
                summary: t(\\\`局部的\${cat.labelZh}结果。\\\`, \\\`Stage 3 \${cat.labelEn} result.\\\`),
                content: formatArtifactContent(catJson, 'json'),
                actions: [
                    {
                        key: \\\`reimport-stage3-\${cat.key}-and-rerun\\\`,
                        label: t(cat.btnZh, cat.btnEn),
                        icon: 'refresh',
                        onClick: async () => {
                            await handleImportStageArtifact({
                                content: catJson,
                                importType: 'json',
                                label: \\\`stage3 \${cat.key} json\\\`,
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
                ],
                placeholder: t(\\\`尚未返回\${cat.labelZh}结果。\\\`, \\\`No \${cat.labelEn} output yet.\\\`),
            });\`;

if (content.includes(badChunk)) {
    content = content.replace(badChunk, goodChunk);
    fs.writeFileSync(filePath, content, 'utf-8');
    console.log('Fixed syntax and stage3 actions using string chunk!');
} else {
    console.log('Could not find bad chunk.');
}
