const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');

text = text.replace(/\r\n/g, '\n');

// 1. Inject hook
const hookSnippet = "    const functionApiConfigs = useFunctionApis('script_analysis');\n";
const targetRegex1 = /export const ScriptEditor = \(\{[\s\S]*?\} \)=> \{\n/;
if (!text.includes("useFunctionApis('script_analysis')")) {
    text = text.replace(targetRegex1, match => match + hookSnippet);
    console.log('Hook injected via Regex');
}

// 2. Inject component
const targetRegex2 = /                    \{isRawMode && \(\n                        <>\n                            <button\n                                onClick=\{handleAnalysisClick\}/;
const replaceWith = "                    {isRawMode && (\n                        <>\n                            <FunctionApiSelector functionName=\"script_analysis\" configs={functionApiConfigs} />\n                            <button\n                                onClick={handleAnalysisClick}";
if (!text.includes("<FunctionApiSelector")) {
    text = text.replace(targetRegex2, replaceWith);
    console.log('Component injected via Regex');
}

fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
