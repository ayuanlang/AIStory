import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { X, Check, Loader2, DollarSign, Wallet } from 'lucide-react';
import { getUiLang, tUI } from '../lib/uiLang';

const RechargeModal = ({ onClose, onSuccess }) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);
    const [step, setStep] = useState('select'); // select, pay, success
    const [amount, setAmount] = useState(10);
    const [customAmount, setCustomAmount] = useState('');
    const [plans, setPlans] = useState([]);
    const [order, setOrder] = useState(null);
    const [loading, setLoading] = useState(false);
    const pollIntervalRef = React.useRef(null);

    // Initial load: Get plans
    useEffect(() => {
        api.get('/billing/recharge/plans').then(res => {
            setPlans(res.data);
        }).catch(err => console.error("Failed to load plans", err));
        
        return () => {
             if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        };
    }, []);

    const getRateForAmount = (amt) => {
        const plan = plans.find(p => amt >= p.min_amount && amt <= p.max_amount);
        return plan ? plan.credit_rate : 100; // Default fallback
    };

    const getBonusForAmount = (amt) => {
        const plan = plans.find(p => amt >= p.min_amount && amt <= p.max_amount);
        return plan ? plan.bonus : 0;
    };

    const handleCreateOrder = async () => {
        const finalAmount = customAmount ? parseInt(customAmount) : amount;
        if (!finalAmount || finalAmount <= 0) return;

        setLoading(true);
        try {
            const res = await api.post('/billing/recharge/create', { amount: finalAmount });
            setOrder(res.data);
            setStep('pay');
            startPolling(res.data.order_no);
        } catch (e) {
            alert("Create order failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    const startPolling = (orderNo) => {
        const interval = setInterval(async () => {
            try {
                const res = await api.get(`/billing/recharge/status/${orderNo}`);
                if (res.data.status === 'PAID') {
                    clearInterval(interval);
                    setStep('success');
                    if (onSuccess) onSuccess();
                }
            } catch (e) {
                console.error("Poll failed", e);
            }
        }, 2000);
        pollIntervalRef.current = interval;
    };

    const handleMockPay = async () => {
        if (!order) return;
        try {
            await api.post(`/billing/recharge/mock_pay/${order.order_no}`);
            // Polling will catch the success, or we can force it
        } catch (e) {
            alert("Mock Pay failed: " + e.message);
        }
    };

    const selectedAmount = customAmount ? parseInt(customAmount) : amount;
    const rate = getRateForAmount(selectedAmount || 0);
    const bonus = getBonusForAmount(selectedAmount || 0);
    const expectedCredits = (selectedAmount || 0) * rate + bonus;

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
            <div className="bg-zinc-900 border border-white/10 p-6 rounded-xl w-full max-w-md shadow-2xl relative">
                <button 
                    onClick={onClose}
                    className="absolute top-4 right-4 text-zinc-500 hover:text-white transition-colors"
                >
                    <X size={20} />
                </button>

                {step === 'select' && (
                    <div className="space-y-6">
                        <div className="text-center">
                            <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-3">
                                <Wallet className="w-6 h-6 text-primary" />
                            </div>
                            <h3 className="text-xl font-bold">{t('充值点数', 'Top Up Credits')}</h3>
                            <p className="text-sm text-zinc-400 mt-1">{t('选择充值金额', 'Select an amount to recharge')}</p>
                        </div>

                        <div className="grid grid-cols-3 gap-3">
                            {[10, 50, 100, 200, 500].map(amt => (
                                <button
                                    key={amt}
                                    onClick={() => { setAmount(amt); setCustomAmount(''); }}
                                    className={`p-3 rounded-lg border text-sm font-medium transition-all ${
                                        amount === amt && !customAmount
                                            ? 'bg-primary text-black border-primary' 
                                            : 'bg-zinc-800 border-zinc-700 hover:border-zinc-500'
                                    }`}
                                >
                                    ￥{amt}
                                </button>
                            ))}
                            <div className="relative">
                                <input 
                                    type="number" 
                                    placeholder={t('自定义', 'Custom')}
                                    className={`w-full h-full bg-zinc-800 border rounded-lg p-3 text-center text-sm outline-none transition-all ${
                                        customAmount ? 'border-primary ring-1 ring-primary' : 'border-zinc-700 focus:border-zinc-500'
                                    }`}
                                    value={customAmount}
                                    onChange={(e) => { setCustomAmount(e.target.value); setAmount(0); }}
                                    onFocus={() => setAmount(0)}
                                />
                            </div>
                        </div>

                        <div className="bg-zinc-800/50 p-4 rounded-lg border border-white/5 space-y-2">
                            <div className="flex justify-between text-sm">
                                <span className="text-zinc-400">{t(`￥${selectedAmount || 0} 对应汇率`, `Rate for ￥${selectedAmount || 0}`)}</span>
                                <span className="font-mono text-zinc-300">{rate} {t('点数', 'credits')} / ￥1</span>
                            </div>
                            <div className="flex justify-between items-center pt-2 border-t border-white/5">
                                <span className="font-medium">{t('可获得', 'You Receive')}</span>
                                <span className="text-xl font-bold text-primary font-mono flex items-center gap-1">
                                    {expectedCredits.toLocaleString()} <span className="text-xs font-normal opacity-70">{t('点数', 'credits')}</span>
                                </span>
                            </div>
                        </div>

                        <button
                            onClick={handleCreateOrder}
                            disabled={loading || !selectedAmount}
                            className="w-full py-3 bg-primary hover:bg-primary/90 text-black font-bold rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? <Loader2 className="animate-spin" /> : <DollarSign size={18} />}
                            {t('微信支付', 'Pay via WeChat')}
                        </button>
                    </div>
                )}

                {step === 'pay' && order && (
                    <div className="text-center space-y-6">
                        <h3 className="text-xl font-bold">{t('扫码支付', 'Scan to Pay')}</h3>
                        <div className="bg-white p-4 rounded-xl inline-block relative">
                             {/* Mock QR Code Overlay */}
                             {order.pay_url && order.pay_url.includes("mock") && (
                                <div className="absolute inset-0 bg-black/60 flex items-center justify-center rounded-xl z-10 m-4">
                                    <p className="text-white text-xs font-bold text-center px-2">{t('模拟模式', 'Mock Mode')}<br/>{t('请点击下方按钮', 'Use Button Below')}</p>
                                </div>
                             )}
                             <div className="w-48 h-48 bg-zinc-100 flex items-center justify-center relative overflow-hidden">
                                {order.pay_url ? (
                                    <img src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(order.pay_url)}`} alt="QR Code" className="w-full h-full opacity-80" />
                                ) : (
                                    <div className="text-black text-xs p-4 break-all">
                                        <p className="font-bold mb-2">{t('模拟二维码', 'Simulated QR Code')}</p>
                                        {order.pay_url}
                                    </div>
                                )}
                             </div>
                        </div>
                        <div className="space-y-2">
                            <p className="font-mono text-2xl font-bold text-primary">￥{order.amount}</p>
                            <p className="text-sm text-zinc-500">{t('订单号', 'Order')}: {order.order_no}</p>
                        </div>
                        
                        <div className="pt-4 border-t border-white/10">
                             {order.pay_url && order.pay_url.includes("mock") ? (
                                <>
                                    <p className="text-xs text-orange-400 mb-3">{t('开发模式：点击下方按钮模拟支付成功。', 'Development Mode: Click below to simulate successful payment.')}</p>
                                    <button 
                                        onClick={handleMockPay}
                                        className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded text-sm text-zinc-300 transition-colors"
                                    >
                                        {t('模拟扫码支付成功', 'Simulate Scan & Pay Success')}
                                    </button>
                                </>
                             ) : (
                                <p className="text-xs text-zinc-500">
                                    {t('请在手机上完成支付确认。', 'Please verify payment on your phone.')}
                                </p>
                             )}
                        </div>
                    </div>
                )}

                {step === 'success' && (
                    <div className="text-center py-8 space-y-4">
                        <div className="w-16 h-16 bg-green-500/20 text-green-500 rounded-full flex items-center justify-center mx-auto mb-4">
                            <Check size={32} />
                        </div>
                        <h3 className="text-2xl font-bold text-white">{t('支付成功！', 'Payment Successful!')}</h3>
                        <p className="text-zinc-400">{t('点数已添加到你的账户。', 'Your credits have been added to your account.')}</p>
                        <button 
                            onClick={onClose}
                            className="w-full py-3 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-lg text-white font-medium mt-4 transition-colors"
                        >
                            {t('返回应用', 'Return to App')}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default RechargeModal;
