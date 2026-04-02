
const fs = require("fs");
let code = fs.readFileSync("src/pages/editor/components/ScriptEditor.jsx", "utf8");

code = code.replace(/                          <\/>\r?\n                      \)\}/, `                          </div>\n                      )}`);
code = code.replace(/                          <\/>\r?\n                      \)\}\r?\n                      \{\!isRawMode && \(/, `                          </div>\n                      )}\n                      {!isRawMode && (`);

// There is one in ScriptEditor, let me confirm by reading:
const lines = code.split("\n");
for(let i=0; i<lines.length; i++) {
   if (lines[i].includes("</>") && lines[i+1] && lines[i+1].includes(")}")) {
       lines[i] = lines[i].replace("</>", "</div>");
       console.log("fixed line " + i);
   }
}
fs.writeFileSync("src/pages/editor/components/ScriptEditor.jsx", lines.join("\n"), "utf8");

