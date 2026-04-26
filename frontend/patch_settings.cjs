const fs = require('fs');

let code = fs.readFileSync('C:/AS/AIStory/frontend/src/pages/Settings.jsx', 'utf-8');

// Inject "Invoice" column header
code = code.replace(
    /<th scope="col" className="px-6 py-3 text-right text-xs font-medium text-cyan-200 uppercase tracking-wider">\s*\{t\('操作', 'Actions'\)\}\s*<\/th>/,
    `<th scope="col" className="px-6 py-3 text-center text-xs font-medium text-cyan-200 uppercase tracking-wider">\n                                            {t('发票', 'Invoice')}\n                                        </th>\n                                        <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-cyan-200 uppercase tracking-wider">\n                                            {t('操作', 'Actions')}\n                                        </th>`
);

// Inject "Invoice" cell
code = code.replace(
    /<td className="px-6 py-4 whitespace-nowrap text-sm text-right font-medium">/,
    `<td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                                            {t?.details?.task_type === 'recharge' && t?.details?.payment_order_id && t?.details?.invoice_status === 'UNINVOICED' && (
                                                <button onClick={() => {}} className="px-3 py-1 rounded bg-blue-600/80 hover:bg-blue-500 text-white text-xs font-medium transition-colors border border-blue-400/30">索要发票</button>
                                            )}
                                            {t?.details?.task_type === 'recharge' && t?.details?.invoice_status === 'REQUESTING' && (<span className="text-cyan-300 text-xs">开票中</span>)}
                                            {t?.details?.task_type === 'recharge' && t?.details?.invoice_status === 'INVOICED' && (<span className="text-green-400 text-xs">已开票</span>)}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-medium">`
);

fs.writeFileSync('C:/AS/AIStory/frontend/src/pages/Settings.jsx', code);
console.log('Patched Settings.jsx');