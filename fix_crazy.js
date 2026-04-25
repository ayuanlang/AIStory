const fs = require('fs');
const file = 'C:/AS/AIStory/frontend/src/pages/editor/components/SubjectLibrary.jsx';
let content = fs.readFileSync(file, 'utf8');

// Replace any occurrence of the U+FFFD character followed by ? and , '
// The error output says `请稍后?, '`
// It could just be `?`
let old = content;
content = content.replace(/\?\s*,\s*'/g, "。', '");

if (old !== content) {
    fs.writeFileSync(file, content, 'utf8');
    console.log('Replaced ?, \'');
} else {
    // Maybe it's just some non-ASCII byte that node reads differently.
    // Let's replace any character before `, '` that is NOT A QUOTE and NOT an ascii character.
    // Meaning `t('.....X, '` where X is not ascii. Wait, the problem is it's missing the single quote before the comma!
    let patched = content.replace(/(t\([^',]+(?:\,(?![ ]'))*?[^'])\,\s*'/g, "$1', '");
    if (patched !== content) {
        fs.writeFileSync(file, patched, 'utf8');
        console.log('General regex replaced missing quotes before comma');
    } else {
        console.log('No matches found for general regex either.');
    }
}
