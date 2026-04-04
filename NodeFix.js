const fs = require("fs");
const file = "c:\\AIStory\\frontend\\src\\pages\\editor\\components\\ScriptEditor.jsx";
let content = fs.readFileSync(file, "utf8");

const bad = "if (onLog) onLog(\\Failed to start auto AI shots: \\, 'error');";
const good = "if (onLog) onLog(`Failed to start auto AI shots: ${batchErr?.message || batchErr}`, 'error');";

content = content.split(bad).join(good);
fs.writeFileSync(file, content);
console.log("Done!");
