const fs = require('fs');

let code = fs.readFileSync('C:/AS/AIStory/frontend/src/pages/Settings.jsx', 'utf-8');

// Header
code = code.replace(
    '<th className="p-3 text-right">{t(\'金额\', \'Amount\')}</th>',
    '<th className="p-3 text-center w-24">{t(\'发票\', \'Invoice\')}</th>\n                                                  <th className="p-3 text-right">{t(\'金额\', \'Amount\')}</th>'
);

// Cell
code = code.replace(
    /<td className="p-3 text-right font-mono">\s*<div className="flex flex-col items-end gap-1">/,
    `<td className="p-3 text-center align-middle whitespace-nowrap">
                                                        {txn.details?.task_type === 'recharge' && txn.details?.payment_order_id && txn.details?.invoice_status === 'UNINVOICED' && (
                                                            <button onClick={() => {}} className="px-3 py-1 rounded bg-[#2a6fd9] hover:bg-[#3b82f6] text-white text-xs font-medium cursor-pointer transition-colors border border-blue-400/30">
                                                                {t('索要发票', 'Request Invoice')}
                                                            </button>
                                                        )}
                                                        {txn.details?.task_type === 'recharge' && txn.details?.invoice_status === 'REQUESTING' && (
                                                            <span className="text-cyan-400 text-xs px-2 py-1 rounded bg-cyan-400/10 border border-cyan-400/20">{t('开票中', 'Requesting')}</span>
                                                        )}
                                                        {txn.details?.task_type === 'recharge' && txn.details?.invoice_status === 'INVOICED' && (
                                                            <span className="text-green-400 text-xs px-2 py-1 rounded bg-green-400/10 border border-green-400/20">{t('已开票', 'Invoiced')}</span>
                                                        )}
                                                    </td>
                                                    <td className="p-3 text-right font-mono">
                                                        <div className="flex flex-col items-end gap-1">`
);

fs.writeFileSync('C:/AS/AIStory/frontend/src/pages/Settings.jsx', code);
console.log('Patched Settings.jsx');