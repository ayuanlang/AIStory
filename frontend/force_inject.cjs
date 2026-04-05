const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');
const search = "                    {isRawMode && (\n                        <>\n                            <button\n                                onClick={handleAnalysisClick}";
const inject = "                    {isRawMode && (\n                        <>\n                            <FunctionApiSelector functionName=\"script_analysis\" configs={functionApiConfigs} />\n                            <button\n                                onClick={handleAnalysisClick}";

if (text.includes(search)) {
    text = text.replace(search, inject);
    fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
    console.log("Injected Successfully!");
} else {
    console.log("Could not find the anchor point for injection.");
    // Log what is around handleAnalysisClick to see why it didn't match
    const idx = text.indexOf("onClick={handleAnalysisClick}");
    console.log("Context around handleAnalysisClick:", JSON.stringify(text.substring(idx - 100, idx + 100)));
}
