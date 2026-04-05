const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');

// Normalize newlines just in case
text = text.replace(/\r\n/g, '\n');

// 1. Inject hook
const hookSnippet = "    const functionApiConfigs = useFunctionApis('script_analysis');\n";
const target1 = "export const ScriptEditor = ({ activeEpisode, projectId, project, onUpdateScript, onUpdateEpisodeInfo, onLog, onImportText, onSwitchToScenes, uiLang = 'zh' }) => {\n";

if (text.includes(target1) && !text.includes("useFunctionApis('script_analysis')")) {
    text = text.replace(target1, target1 + hookSnippet);
    console.log('Hook injected');
}

// 2. Inject component
const target2 = "                    {isRawMode && (\n                        <>\n                            <button\n                                onClick={handleAnalysisClick}";
const componentSnippet = "                    {isRawMode && (\n                        <>\n                            <FunctionApiSelector functionName=\"script_analysis\" configs={functionApiConfigs} />\n                            <button\n                                onClick={handleAnalysisClick}";

if (text.includes(target2) && !text.includes("<FunctionApiSelector")) {
    text = text.replace(target2, componentSnippet);
    console.log('Component injected');
}

fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
