
const fs = require('fs');
let code = fs.readFileSync('api.js', 'utf8');

const snip = \export const getApiRoutingMode = async () => {
    const response = await api.get('/settings/system/api_routing_mode');
    return response.data;
};

export const updateApiRoutingMode = async (payload) => {
    const response = await api.post(\\\/settings/system/api_routing_mode\\\, payload);
    return response.data;
};\;

const parts = code.split(snip);
if (parts.length > 2) {
    code = parts[0] + snip + parts.slice(1).join('');
    fs.writeFileSync('api.js', code);
    console.log('Fixed');
} else {
    console.log('Not found or only one');
}
\;
