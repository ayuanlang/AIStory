const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');

const doubleInject = "<FunctionApiSelector functionName=\"script_analysis\" configs={functionApiConfigs} />\n                            <FunctionApiSelector functionName=\"script_analysis\" configs={functionApiConfigs} />\n                            ";

const singleInject = "<FunctionApiSelector functionName=\"script_analysis\" configs={functionApiConfigs} />\n                            ";

text = text.replace(doubleInject, singleInject);
fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
console.log("Fixed double injection!");
