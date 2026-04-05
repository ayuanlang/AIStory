const fs = require('fs');
let text = fs.readFileSync('src/pages/editor/components/ScriptEditor.jsx', 'utf-8');

text = text.replace(/\r\n/g, '\n');

// 1. view switch
const idx1 = text.indexOf('Switch to Table View');
if (idx1 !== -1) {
    const start1 = text.lastIndexOf('                    {segments.length > 0 && (\n                        <button ', idx1);
    const end1 = text.indexOf('                    )}\n', idx1) + 23;
    if (start1 !== -1 && end1 > 22) {
        text = text.substring(0, start1) + text.substring(end1);
        console.log('Removed View Toggle');
    }
}

// 2. import button
const idx2 = text.indexOf('Manual Import Model Analysis Result');
if (idx2 !== -1) {
    const start2 = text.lastIndexOf('                    <button\n                        onClick={() => doImportText', idx2);
    const end2 = text.indexOf('                    </button>\n', idx2) + 30;
    if (start2 !== -1 && end2 > 29) {
        text = text.substring(0, start2) + text.substring(end2);
        console.log('Removed import');
    }
}

// 3. workspace
const start_str = '                <div className="border-t border-white/10 bg-black/10 shrink-0">';
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
    
    pos++;
    
    const before = text.substring(0, start_idx);
    const middle = text.substring(start_idx, pos);
    const after = text.substring(pos);
    
    // Using string concat with real new lines because PowerShell escapes suck
    const newMiddle = "                {isSuperuser && (\n" + middle + "\n                )}\n";
    text = before + newMiddle + after;
    console.log('Wrapped output workspace');
}

fs.writeFileSync('src/pages/editor/components/ScriptEditor.jsx', text);
