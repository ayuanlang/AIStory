
const fs = require("fs");
let code = fs.readFileSync("frontend/src/pages/editor/components/ScriptEditor.jsx", "utf8");

code = code.replace(
    /                                  \}\)\}\r?\n                              <\/button>\r?\n                              \{isAnalyzing && \(/g,
    `                                  )}
                              </button>
                          </div>
                              {isAnalyzing && (`
);

fs.writeFileSync("frontend/src/pages/editor/components/ScriptEditor.jsx", code, "utf8");

