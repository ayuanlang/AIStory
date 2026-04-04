const fs = require('fs');
const file = 'c:\\AIStory\\frontend\\src\\pages\\editor\\components\\ScriptEditor.jsx';
let content = fs.readFileSync(file, 'utf8');

const anchor = '{isRawMode && (\\n                        <>';
const replacement = '{isRawMode && (\\n                        <>\\n                            <label className="flex items-center gap-2 px-3 py-1 bg-white/5 rounded-lg border border-white/10 cursor-pointer hover:bg-white/10 transition-colors">\\n                                <input type="checkbox" checked={autoGenerateShots} onChange={(e) => setAutoGenerateShots(e.target.checked)} disabled={isAnalyzing} className="w-4 h-4 rounded" />\\n                                <span className="text-sm font-medium text-white/90">{t("自动生成分镜", "Auto-generate Shots")}</span>\\n                            </label>';

content = content.replace(anchor, replacement);
fs.writeFileSync(file, content);
console.log('Done!');
