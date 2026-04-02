
const fs = require('fs');
let code = fs.readFileSync('frontend/src/services/api.js', 'utf8');

const regex = /export const getApiRoutingMode = async \(\) => \{\n    const response = await api\.get\('\\/settings\\/system\\/api_routing_mode'\);\n    return response\.data;\n\};\n\nexport const updateApiRoutingMode = async \(payload\) => \{\n    const response = await api\.post\\\(\\\\\/settings\\/system\\/api_routing_mode\\\\\\, payload\);\n    return response\.data;\n\};\n/g;

let count = 0;
code = code.replace(regex, (match) => {
    count++;
    if(count === 1) return match;
    return '';
});

fs.writeFileSync('frontend/src/services/api.js', code, 'utf8');
console.log('Removed duplicate endpoints.');

