
const fs = require('fs');
let code = fs.readFileSync('c:/AIStory/frontend/src/services/api.js', 'utf8');

const toAdd = \
export const getApiRoutingConfig = async () => {
    const response = await api.get('/settings/system/api-routing-config');
    return response.data;
};

export const updateApiRoutingConfig = async (payload) => {
    const response = await api.put('/settings/system/api-routing-config', payload);
    return response.data;
};
\;

code = code.replace('// -- Function API Configs --', '// -- Function API Configs --' + '\\n' + toAdd);
fs.writeFileSync('c:/AIStory/frontend/src/services/api.js', code, 'utf8');

