const fs = require("fs");
let code = fs.readFileSync("frontend/src/services/api.js", "utf8");

const addition = `
export const getApiRoutingMode = async () => {
    const response = await api.get('/settings/system/api_routing_mode');
    return response.data;
};

export const updateApiRoutingMode = async (payload) => {
    const response = await api.post(\`/settings/system/api_routing_mode\`, payload);
    return response.data;
};
`;

code += "\n" + addition;
fs.writeFileSync("frontend/src/services/api.js", code, "utf8");
console.log("Added api endpoints.");