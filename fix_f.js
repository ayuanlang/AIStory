const fs = require('fs');
let code = fs.readFileSync('frontend/src/components/FunctionApiSelector.jsx', 'utf-8');

const oldRegex = /<option key=\{api\.system_api_id\}.*?<\/option>/gs;

const newOption = '<option key={api.system_api_id} value={api.system_api_id}>' +
                        '{api.alias || (api.system_api_name || \"API \" + api.system_api_id)} ' +
                        '{api.applicable_languages && api.applicable_languages.length > 0 ? \" (\" + api.applicable_languages.join(\", \") + \")\" : \"\"}' +
                        '{api.is_fallback ? \" (备用)\" : \"\"}' +
                    '</option>';

code = code.replace(oldRegex, newOption);
fs.writeFileSync('frontend/src/components/FunctionApiSelector.jsx', code, 'utf-8');
console.log('Fixed FunctionApiSelector');
