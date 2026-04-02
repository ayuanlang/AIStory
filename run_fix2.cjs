const fs = require('fs');
let code = fs.readFileSync('frontend/src/components/FunctionApiSelector.jsx', 'utf8');

code = code.replace(/<span className="text-xs text-white\/50 whitespace-nowrap">API:<\/span>\s*/g, '');

fs.writeFileSync('frontend/src/components/FunctionApiSelector.jsx', code, 'utf8');
console.log('Removed API label');