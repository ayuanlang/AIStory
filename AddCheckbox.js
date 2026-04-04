const fs = require("fs");
const file = "c:\\AIStory\\frontend\\src\\pages\\editor\\components\\ScriptEditor.jsx";
let content = fs.readFileSync(file, "utf8");

const anchor = '{isRawMode && (\r\n                        <>\r\n                            <button';
const anchor2 = '{isRawMode && (\n                        <>\n                            <button';

const replacement = '{isRawMode && (\n                        <>\n                            <label className="flex items-center gap-2 px-3 py-1 bg-white/5 rounded-lg border border-white/10 cursor-pointer hover:bg-white/10 transition-colors">\n                                <input type="checkbox" checked={autoGenerateShots} onChange={(e) => setAutoGenerateShots(e.target.checked)} disabled={isAnalyzing} className="w-4 h-4 rounded border-white/20 bg-black/50 text-purple-500 focus:ring-purple-500/50 focus:ring-offset-0 disabled:opacity-50" />\n                                <span className="text-sm font-medium text-white/90">{t("自动生成分镜", "Auto-generate Shots")}</span>\n                            </label>\n                            <button';

content = content.replace(anchor, replacement);
content = content.replace(anchor2, replacement);
fs.writeFileSync(file, content);
console.log("Done adding checkbox UI!");
