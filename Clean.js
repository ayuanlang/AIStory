const fs = require("fs");
const file = "c:\\AIStory\\frontend\\src\\pages\\editor\\components\\ScriptEditor.jsx";
let content = fs.readFileSync(file, "utf8");

content = content.replace("<label className=flex\r\n                            <button", "<button");
content = content.replace("<label className=flex\n                            <button", "<button");

fs.writeFileSync(file, content);
console.log("Done!");
