
with open('api.js', 'r', encoding='utf-8') as f:
    orig = f.read()

import re
code = re.sub(r'export const getApiRoutingMode = async.*?updateApiRoutingMode = async.*?return response.data;\n};\n', '', orig, flags=re.DOTALL)

code += '''
export const getApiRoutingMode = async () => {
    const response = await api.get('/settings/system/api_routing_mode');
    return response.data;
};

export const updateApiRoutingMode = async (payload) => {
    const response = await api.post(/settings/system/api_routing_mode, payload);
    return response.data;
};
'''

with open('api.js', 'w', encoding='utf-8') as f:
    f.write(code)

print('success')

