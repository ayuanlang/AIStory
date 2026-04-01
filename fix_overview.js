const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

// Find the Project Overview render area (h2 label)
const h2Regex = /<h2 className="text-2xl font-bold">\{mode === 'generator' \? t\('生成器', 'Generators'\) : t\('项目总览', 'Project Overview'\)\}<\/h2>/;

const replacement = `<div className="flex items-center gap-4">
                    <h2 className="text-2xl font-bold">{mode === 'generator' ? t('生成器', 'Generators') : t('项目总览', 'Project Overview')}</h2>
                    {mode === 'overview' && (
                        <div className="flex items-center px-3 py-1 rounded-full bg-primary/20 border border-primary/30 text-primary text-sm font-medium">
                            {t('阶段', 'Stage')}: {
                                (info?.workflow_stage === 'montage') ? t('剪辑', 'Montage') :
                                (info?.workflow_stage === 'shots') ? t('分镜', 'Shots') :
                                (info?.workflow_stage === 'subjects') ? t('资产', 'Assets') :
                                t('剧本', 'Script')
                            }
                        </div>
                    )}
                </div>`;

content = content.replace(h2Regex, replacement);

fs.writeFileSync('frontend/src/pages/Editor.jsx', content);
console.log('ProjectOverview updated');
