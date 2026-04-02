
const fs = require("fs");
let code = fs.readFileSync("frontend/src/pages/editor/components/ScriptEditor.jsx", "utf8");

code = code.replace(
    /\{isRawMode && \(\s*<>\s*<button\s*onClick=\{handleAnalysisClick\}\s*disabled=\{isAnalyzing\}/g,
    `{isRawMode && (
                          <div className="flex items-center gap-2">
                              <FunctionApiSelector functionName="script_analysis" configs={functionApiConfigs} />
                              <button
                                  onClick={handleAnalysisClick} 
                                  disabled={isAnalyzing}`
);

code = code.replace(
    /export const ScriptEditor = \(\{[^}]*\}\) => \{/,
    `$&
    const functionApiConfigs = useFunctionApis();`
);

fs.writeFileSync("frontend/src/pages/editor/components/ScriptEditor.jsx", code, "utf8");

