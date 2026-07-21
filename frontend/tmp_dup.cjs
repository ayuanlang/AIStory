const fs = require("fs");
const path = "c:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx";
const lines = fs.readFileSync(path, "utf8").split(/\r?\n/);
const componentStart = lines.findIndex((l) => /export const ScriptEditor/.test(l));
const counts = new Map();
const first = new Map();
const declRe = /^\s{4}(?:const|let|function)\s+([A-Za-z_$][\w$]*)/;
for (let i = componentStart; i < lines.length; i++) {
  const m = lines[i].match(declRe);
  if (!m) continue;
  const name = m[1];
  counts.set(name, (counts.get(name) || 0) + 1);
  if (!first.has(name)) first.set(name, i + 1);
}
const dups = [...counts.entries()].filter(([, n]) => n > 1).sort((a,b) => b[1]-a[1]);
console.log("duplicate bindings:", dups.length);
for (const [name, n] of dups.slice(0, 50)) {
  const locs = [];
  for (let i = componentStart; i < lines.length; i++) {
    const m = lines[i].match(declRe);
    if (m && m[1] === name) locs.push(i + 1);
  }
  console.log(name + " x" + n + " @ " + locs.join(", "));
}
