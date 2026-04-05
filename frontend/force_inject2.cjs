const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');

const targetIdx = text.indexOf("onClick={handleAnalysisClick}");
const btnStart = text.lastIndexOf("<button", targetIdx);

const inject = "<FunctionApiSelector functionName=\"script_analysis\" configs={functionApiConfigs} />\n                            ";

text = text.substring(0, btnStart) + inject + text.substring(btnStart);
fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
console.log("Injected Successfully!");
