const fs = require("fs");
const file = "src/pages/editor/components/ShotsView.jsx";
let content = fs.readFileSync(file, "utf8");

const metadataRegex = /\s*\{\/\* Metadata \*\/\}\s*<div className="space-y-3 pt-4 border-t border-white\/10">[\s\S]*?(?=\s*<div className="grid grid-cols-2 gap-4 pt-4 border-t border-white\/10 text-xs text-muted-foreground">)/;
content = content.replace(metadataRegex, "\n\n                            ");

const gridRegex = /<div className="grid grid-cols-2 gap-4 pt-4 border-t border-white\/10 text-xs text-muted-foreground">\s*<InputGroup label="Shot Number" value=\{editingShot\.shot_id\} onChange=\{\(v\) => \{ setEditingShot\(\{\.\.\.editingShot, shot_id: v\}\) \}\} \/>\s*<InputGroup label="Duration \(s\)" value=\{editingShot\.duration\} onChange=\{v => setEditingShot\(\{\.\.\.editingShot, duration: v\}\)\} \/>\s*<\/div>/;

const newGrid = `<div className="grid grid-cols-1 pt-4 border-t border-white/10 text-xs text-muted-foreground">
                                <InputGroup label="Duration (s)" value={editingShot.duration} onChange={v => setEditingShot({...editingShot, duration: v})} />
                            </div>`;

content = content.replace(gridRegex, newGrid);

fs.writeFileSync(file, content, "utf8");
console.log("Done");
