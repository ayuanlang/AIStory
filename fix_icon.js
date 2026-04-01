const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');

// The replacement strategy
const target = /{item\.id !== \"generator\" \? item\.label : null}/g;
if (content.match(target)) {
    content = content.replace(target, '<Icon className=\"w-3.5 h-3.5\" />\n                                        {item.id !== \"generator\" ? item.label : null}');
    fs.writeFileSync('frontend/src/pages/Editor.jsx', content);
    console.log('Icon replaced');
} else {
    console.log('Target not found');
}
