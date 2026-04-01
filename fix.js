const fs = require('fs');
let content = fs.readFileSync('frontend/src/pages/Editor.jsx', 'utf8');
content = content.replace(/t\('\?\?\?', 'Generator'\)/g, "t('Éú³ÉÆ÷', 'Generator')");
fs.writeFileSync('frontend/src/pages/Editor.jsx', content, 'utf8');
console.log('Done!');
