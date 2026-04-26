import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { apiGetInvoiceProfiles, apiCreateInvoiceProfile, apiRequestInvoice } from '../../services/api';

const InvoiceRequestModal = ({ orderId, amount, onClose, onSuccess }) => {
    const { t } = useTranslation();
    const [profiles, setProfiles] = useState([]);
    const [selectedProfileId, setSelectedProfileId] = useState(null);
    const [isCreatingNew, setIsCreatingNew] = useState(false);
    
    const [newProfile, setNewProfile] = useState({
        type: 'ENTERPRISE',
        title: '',
        tax_number: '',
        email: ''
    });
    
    const [email, setEmail] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        loadProfiles();
    }, []);

    const loadProfiles = async () => {
        try {
            const data = await apiGetInvoiceProfiles();
            setProfiles(data);
            if (data.length > 0) {
                setSelectedProfileId(data[0].id);
                setEmail(data[0].email || '');
            } else {
                setIsCreatingNew(true);
            }
        } catch (err) {
            console.error('Failed to load profiles:', err);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        try {
            let profileId = selectedProfileId;
            
            if (isCreatingNew) {
                if (!newProfile.title) throw new Error(t('请输入发票抬头', 'Please enter invoice title'));
                if (newProfile.type === 'ENTERPRISE' && !newProfile.tax_number) {
                    throw new Error(t('请输入企业税号', 'Please enter tax number'));
                }
                const created = await apiCreateInvoiceProfile({
                    ...newProfile,
                    email: email
                });
                profileId = created.id;
            }

            if (!email) throw new Error(t('请输入接收邮箱', 'Please enter email address'));

            await apiRequestInvoice({
                order_id: orderId,
                profile_id: profileId,
                email: email
            });

            onSuccess();
        } catch (err) {
            setError(err.message || t('请求开票失败', 'Failed to request invoice'));
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="w-full max-w-md bg-[#0a192bc0] border border-white/10 shadow-2xl rounded-xl overflow-hidden">
                <div className="flex border-b border-white/10 items-center justify-between p-4">
                    <h3 className="text-base font-medium text-white">{t('索要发票', 'Request Invoice')}</h3>
                    <button onClick={onClose} className="p-1 rounded text-white/50 hover:bg-white/10 hover:text-white transition-colors">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/></svg>
                    </button>
                </div>
                
                <div className="p-5 max-h-[70vh] overflow-y-auto">
                    <div className="mb-4 p-3 bg-red-400/10 border border-red-400/20 rounded-lg text-sm flex justify-between">
                        <span className="text-zinc-300">{t('开票金额', 'Invoice Amount')}:</span>
                        <span className="font-mono text-red-400 font-bold">¥ {amount.toFixed(2)}</span>
                    </div>

                    {error && (
                        <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 text-red-200 text-xs rounded-lg">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4 text-sm">
                        {profiles.length > 0 && (
                            <div className="space-y-2">
                                <label className="text-zinc-400 text-xs uppercase tracking-wider">{t('选择抬头', 'Select Profile')}</label>
                                <div className="space-y-2">
                                    {profiles.map(p => (
                                        <div 
                                            key={p.id} 
                                            onClick={() => {
                                                setSelectedProfileId(p.id);
                                                setIsCreatingNew(false);
                                                if (p.email && p.email !== email) setEmail(p.email);
                                            }}
                                            className={`p-3 flex items-center gap-3 border rounded-lg cursor-pointer transition-colors ${
                                                selectedProfileId === p.id && !isCreatingNew 
                                                ? 'border-blue-500 bg-blue-500/10' 
                                                : 'border-white/10 hover:border-white/20 hover:bg-white/5'
                                            }`}
                                        >
                                            <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${selectedProfileId === p.id && !isCreatingNew ? 'border-blue-400' : 'border-white/30'}`}>
                                                {selectedProfileId === p.id && !isCreatingNew && <div className="w-2 h-2 rounded-full bg-blue-400"></div>}
                                            </div>
                                            <div className="flex-1">
                                                <div className="font-medium text-zinc-200">{p.title}</div>
                                                {p.type === 'ENTERPRISE' && <div className="text-xs text-zinc-500 font-mono mt-1">{p.tax_number}</div>}
                                            </div>
                                        </div>
                                    ))}
                                    
                                    <div 
                                        onClick={() => setIsCreatingNew(true)}
                                        className={`p-3 flex items-center gap-3 border rounded-lg cursor-pointer transition-colors ${
                                            isCreatingNew 
                                            ? 'border-blue-500 bg-blue-500/10' 
                                            : 'border-white/10 hover:border-white/20 hover:bg-white/5'
                                        }`}
                                    >
                                        <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${isCreatingNew ? 'border-blue-400' : 'border-white/30'}`}>
                                            {isCreatingNew && <div className="w-2 h-2 rounded-full bg-blue-400"></div>}
                                        </div>
                                        <div className="font-medium text-zinc-200">{t('使用新抬头', 'Use New Profile')}</div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {isCreatingNew && (
                            <div className="p-4 bg-black/40 border border-white/5 rounded-lg space-y-4">
                                <div className="space-y-1.5">
                                    <label className="text-zinc-400 text-xs">{t('抬头类型', 'Type')}</label>
                                    <div className="flex gap-2">
                                        <button type="button" onClick={() => setNewProfile({...newProfile, type: 'ENTERPRISE'})} className={`flex-1 py-1.5 rounded text-xs transition-colors ${newProfile.type === 'ENTERPRISE' ? 'bg-primary text-black font-medium' : 'bg-white/10 text-zinc-300 hover:bg-white/20'}`}>
                                            {t('企业', 'Enterprise')}
                                        </button>
                                        <button type="button" onClick={() => setNewProfile({...newProfile, type: 'PERSONAL'})} className={`flex-1 py-1.5 rounded text-xs transition-colors ${newProfile.type === 'PERSONAL' ? 'bg-primary text-black font-medium' : 'bg-white/10 text-zinc-300 hover:bg-white/20'}`}>
                                            {t('个人/非企业单位', 'Personal')}
                                        </button>
                                    </div>
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-zinc-400 text-xs">{t('发票抬头', 'Invoice Title')} <span className="text-red-400">*</span></label>
                                    <input 
                                        type="text" 
                                        value={newProfile.title}
                                        onChange={e => setNewProfile({...newProfile, title: e.target.value})}
                                        className="w-full bg-black/50 border border-white/10 rounded-md px-3 py-2 text-zinc-200 focus:outline-none focus:border-primary/50 text-sm"
                                        placeholder={t('请输入发票抬头', 'Please enter invoice title')}
                                    />
                                </div>
                                {newProfile.type === 'ENTERPRISE' && (
                                    <div className="space-y-1.5">
                                        <label className="text-zinc-400 text-xs">{t('企业税号', 'Tax Number')} <span className="text-red-400">*</span></label>
                                        <input 
                                            type="text" 
                                            value={newProfile.tax_number}
                                            onChange={e => setNewProfile({...newProfile, tax_number: e.target.value})}
                                            className="w-full bg-black/50 border border-white/10 rounded-md px-3 py-2 text-zinc-200 focus:outline-none focus:border-primary/50 text-sm font-mono"
                                            placeholder={t('请输入统一社会信用代码', 'Please enter tax number')}
                                        />
                                    </div>
                                )}
                            </div>
                        )}

                        <div className="border-t border-white/10 pt-4 space-y-1.5">
                            <label className="text-zinc-400 text-xs">{t('接收邮箱', 'Email Address')} <span className="text-red-400">*</span></label>
                            <input 
                                type="email" 
                                value={email}
                                onChange={e => setEmail(e.target.value)}
                                className="w-full bg-black/40 border border-white/10 rounded-md px-3 py-2 text-zinc-200 focus:outline-none focus:border-primary/50 text-sm"
                                placeholder={t('用于接收电子发票及通知', 'For receiving electronic invoice')}
                            />
                            <p className="text-[10px] text-zinc-500 mt-1">{t('电子发票将在开具后发送至此邮箱', 'The electronic invoice will be sent to this email after issuance.')}</p>
                        </div>

                    </form>
                </div>
                
                <div className="p-4 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                    <button 
                        type="button" 
                        onClick={onClose}
                        disabled={loading}
                        className="px-4 py-2 text-sm text-zinc-300 hover:text-white transition-colors"
                    >
                        {t('取消', 'Cancel')}
                    </button>
                    <button 
                        onClick={handleSubmit}
                        disabled={loading}
                        className="px-6 py-2 bg-[#2a6fd9] hover:bg-[#3b82f6] text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center min-w-[100px] shadow-lg shadow-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin"></div> : t('提交申请', 'Submit Request')}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default InvoiceRequestModal;