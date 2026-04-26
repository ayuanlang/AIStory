const fs = require('fs');
let code = fs.readFileSync('C:/AS/AIStory/frontend/src/pages/Settings.jsx', 'utf-8');

const target = "<td className={`p-3 text-right font-mono font-bold ${t.amount < 0 ? 'text-red-400' : 'text-green-400'}`}>";

const replacement = `<td className="p-3 text-center align-middle whitespace-nowrap">
                                                        {t.details?.task_type === 'recharge' && t.details?.payment_order_id && t.details?.invoice_status === 'UNINVOICED' && (
                                                            <button onClick={() => {}} className="px-3 py-1 rounded bg-[#2a6fd9] hover:bg-[#3b82f6] text-white text-xs font-medium cursor-pointer transition-colors border border-blue-400/30">
                                                                {t('索要发票', 'Request Invoice') || 'Request Invoice'}
                                                            </button>
                                                        )}
                                                        {t.details?.task_type === 'recharge' && t.details?.invoice_status === 'REQUESTING' && (
                                                            <span className="text-cyan-400 text-xs px-2 py-1 rounded bg-cyan-400/10 border border-cyan-400/20">{t('开票中', 'Requesting') || 'Requesting'}</span>
                                                        )}
                                                        {t.details?.task_type === 'recharge' && t.details?.invoice_status === 'INVOICED' && (
                                                            <span className="text-green-400 text-xs px-2 py-1 rounded bg-green-400/10 border border-green-400/20">{t('已开票', 'Invoiced') || 'Invoiced'}</span>
                                                        )}
                                                    </td>\n                                                      ` + target;

code = code.replace(target, replacement);

fs.writeFileSync('C:/AS/AIStory/frontend/src/pages/Settings.jsx', code);
console.log('Patched cell');