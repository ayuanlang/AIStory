const fs = require('fs');

let code = fs.readFileSync('C:/AS/AIStory/frontend/src/services/api.js', 'utf-8');

const invoiceAPIs = `// Invoices
export const apiGetInvoiceProfiles = async () => {
    return handleResponse(await fetchWithAuth(\`\${API_URL}/api/v1/invoices/profiles\`));
};

export const apiCreateInvoiceProfile = async (profile) => {
    return handleResponse(await fetchWithAuth(\`\${API_URL}/api/v1/invoices/profiles\`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile)
    }));
};

export const apiRequestInvoice = async (request) => {
    return handleResponse(await fetchWithAuth(\`\${API_URL}/api/v1/invoices/request\`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
    }));
};
`;

if (!code.includes('apiGetInvoiceProfiles')) {
    code = code + '\n' + invoiceAPIs;
    fs.writeFileSync('C:/AS/AIStory/frontend/src/services/api.js', code);
    console.log('Added invoice APIs');
} else {
    console.log('Already added');
}