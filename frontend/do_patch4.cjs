const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');

text = text.replace(/\r\n/g, '\n');

// 1. view switch
const viewSwitchRegex = /                    \{segments\.length > 0 && \(\n                        <button[\s\S]*?Switch to Table View[\s\S]*?<\/button>\n                    \)}\n/g;
text = text.replace(viewSwitchRegex, '');
console.log('Removed view switch:', (text.match(/Switch to Table View/) === null));

// 2. import button
const importBtnRegex = /                    <button\n                        onClick=\{[^\n]*doImportText[\s\S]*?Manual Import Model Analysis Result[\s\S]*?<\/button>\n/g;
text = text.replace(importBtnRegex, '');
console.log('Removed import btn:', (text.match(/Manual Import Model Analysis Result/) === null));

// 3. workspace
const start_str = '<div className="border-t border-white/10 bg-black/10 shrink-0">';
const start_idx = text.indexOf(start_str);

if (start_idx !== -1) {
    let depth = 0;
    let pos = start_idx;
    
    while(pos < text.length) {
        if (text.startsWith('<div', pos)) {
            depth++;
            pos += 4;
        } else if (text.startsWith('</div', pos)) {
            depth--;
            pos += 5;
        } else {
            pos++;
        }
        if (depth === 0 && pos > start_idx + 10) break;
    }
    
    // We break when pos reaches the 'v' of '</div>'. We need to include '</div>' which is length 6
    // wait! pos += 5 already moved it past '</div', so it's at '>'. pos++ will move it past '>'.
    // Let's just find the closing '>' from pos.
    while(text[pos] !== '>' && pos < text.length) pos++;
    pos++; 
    
    // Now we also need to include the preceding spaces before start_str to wrap them cleanly? No, JSX doesn't care.
    // However, for formatting it's nice. Let's just wrap it.
    
    // go backwards to grab spaces at start_idx
    let ws_start = start_idx;
    while(ws_start > 0 && text[ws_start - 1] === ' ') ws_start--;
    
    const before = text.substring(0, ws_start);
    const middle = text.substring(ws_start, pos);
    const after = text.substring(pos);
    
    const newMiddle = "                {isSuperuser && (\n" + middle + "\n                )}\n";
    text = before + newMiddle + after;
    console.log('Wrapped output workspace');
} else {
    console.log('Workspace NOT FOUND');
}

fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
