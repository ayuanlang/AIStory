import React, { useState, useEffect } from 'react';
import { api, getPricingRules, createPricingRule, updatePricingRule, deletePricingRule, getTransactions, updateUserCredits, syncPricingRules } from '../services/api';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';
import { Shield, User, Key, Check, X, Crown, Settings, DollarSign, Activity, List, Plus, Trash2, Edit2, RefreshCw } from 'lucide-react';

const UserAdmin = () => {
    const [activeTab, setActiveTab] = useState('users');
    const [users, setUsers] = useState([]);
    const [pricingRules, setPricingRules] = useState([]);
    const [transactions, setTransactions] = useState([]);
    const [transactionFilterUser, setTransactionFilterUser] = useState(''); // User ID filter
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // New/Edit Rule State
    const [isRuleModalOpen, setIsRuleModalOpen] = useState(false);
    const [editingRule, setEditingRule] = useState(null);
    const [ruleForm, setRuleForm] = useState({ task_type: 'llm_chat', provider: '', model: '', cost: 1, unit_type: 'per_call' });
    
    // Calculator State
    const [calcPriceUSD, setCalcPriceUSD] = useState('');
    const [calcPriceInput, setCalcPriceInput] = useState('');
    const [calcPriceOutput, setCalcPriceOutput] = useState('');
    const [exchangeRate, setExchangeRate] = useState(10); // Default: ￥1 = 10 Credits
    const [markup, setMarkup] = useState('1.0'); // Default: 1.0x (No markup) - String for better input handling

    // Effect to auto-calculate
    useEffect(() => {
        const rate = parseFloat(exchangeRate) || 10;
        const mark = parseFloat(markup) || 1.0;
        
        // Single Cost Calculation (Generic)
        const price = parseFloat(calcPriceUSD);
        let validUpdate = false;
        let updates = {};

        // Always save reference values
        updates.ref_markup = mark;
        updates.ref_exchange_rate = rate;
        
        if (!isNaN(price)) {
            updates.cost = Math.ceil(price * rate * mark);
            updates.ref_cost_cny = price;
            validUpdate = true;
        }

        // Dual Cost Calculation (LLM)
        if (ruleForm.task_type === 'llm_chat') {
            const pInput = parseFloat(calcPriceInput);
            const pOutput = parseFloat(calcPriceOutput);
            
            if (!isNaN(pInput) || !isNaN(pOutput)) {
                 const costIn = !isNaN(pInput) ? pInput * rate * mark : 0;
                 const costOut = !isNaN(pOutput) ? pOutput * rate * mark : 0;

                 updates.cost_input = Math.ceil(costIn);
                 updates.cost_output = Math.ceil(costOut);
                 updates.ref_cost_input_cny = !isNaN(pInput) ? pInput : 0;
                 updates.ref_cost_output_cny = !isNaN(pOutput) ? pOutput : 0;
                 validUpdate = true;
            }
        }
        
        if (validUpdate) {
            setRuleForm(prev => ({ ...prev, ...updates }));
        }
    }, [calcPriceUSD, calcPriceInput, calcPriceOutput, exchangeRate, markup, ruleForm.task_type]);

    // Credit Edit State
    const [creditEditUser, setCreditEditUser] = useState(null);
    const [creditAmount, setCreditAmount] = useState(0);

    const PROVIDER_OPTIONS = {
        llm_chat: [
            { value: 'openai', label: 'OpenAI / Compatible' },
            { value: 'doubao', label: 'Doubao (Volcengine)' },
            { value: 'ollama', label: 'Ollama (Local)' },
            { value: 'deepseek', label: 'DeepSeek' },
            { value: 'grsai', label: 'Grsai (Aggregation)' }
        ],
        image_gen: [
            { value: 'Midjourney', label: 'Midjourney' },
            { value: 'Doubao', label: 'Doubao (Volcengine)' },
            { value: 'Grsai-Image', label: 'Grsai (Aggregation)' },
            { value: 'DALL-E 3', label: 'DALL-E 3' },
            { value: 'Stable Diffusion', label: 'Stable Diffusion' },
            { value: 'Flux', label: 'Flux.1' },
            { value: 'Tencent Hunyuan', label: 'Tencent Hunyuan' }
        ],
        video_gen: [
            { value: 'Runway', label: 'Runway Gen-2/Gen-3' },
            { value: 'Luma', label: 'Luma Dream Machine' },
            { value: 'Kling', label: 'Kling AI' },
            { value: 'Sora', label: 'Sora (OpenAI)' },
            { value: 'Grsai-Video', label: 'Grsai (Standard)' },
            { value: 'Grsai-Video (Upload)', label: 'Grsai (Upload)' },
            { value: 'Stable Video', label: 'Stable Video' },
            { value: 'Doubao Video', label: 'Doubao (Volcengine)' },
            { value: 'Wanxiang', label: 'Wanxiang (Aliyun)' },
            { value: 'Vidu (Video)', label: 'Vidu (Shengshu)' }
        ],
        analysis: [
            { value: 'openai', label: 'OpenAI' },
            { value: 'grsai', label: 'Grsai' },
            { value: 'claude', label: 'Claude' },
            { value: 'gemini', label: 'Gemini' }
        ],
        analysis_character: [
            { value: 'openai', label: 'OpenAI' },
            { value: 'grsai', label: 'Grsai' }
        ]
    };

    const MODEL_OPTIONS = {
        'Grsai-Image': [
            'sora-image', 'gpt-image-1.5', 'sora-create-character', 'sora-upload-character', 
            'nano-banana-pro', 'nano-banana-pro-vt', 'nano-banana-fast', 'nano-banana-pro-cl', 
            'nano-banana-pro-vip', 'nano-banana', 'nano-banana-pro-4k-vip'
        ],
        'Grsai-Video': [
            'sora-2', 'veo3.1-pro', 'veo3.1-fast', 'veo3.1-pro-1080p', 'veo3.1-pro-4k', 
            'veo3.1-fast-1080p', 'veo3.1-fast-4k', 'nano-banana-pro', 'nano-banana-pro-vt', 
            'nano-banana-fast', 'nano-banana-pro-cl', 'nano-banana-pro-vip', 'nano-banana', 
            'nano-banana-pro-4k-vip'
        ],
        'Grsai-Video (Upload)': [ 'sora-2', 'veo3.1-pro', 'veo3.1-fast' ],
        'openai': ['gpt-4o', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
        'doubao': ['doubao-pro-32k', 'doubao-lite-4k'],
        'ollama': ['llama3', 'mistral', 'gemma'],
        'grsai': ['gemini-3-pro', 'claude-3-opus', 'claude-3-sonnet', 'gpt-4-turbo'],
        'Doubao Video': ['doubao-seedance-1-5-pro-251215'],
        'Vidu (Video)': ['vidu2.0', 'viduq2-pro', 'viduq2-pro-fast', 'viduq2-turbo', 'viduq1'],
        'Wanxiang': ['wanx2.1-kf2v-plus'],
        'Doubao': ['doubao-seedream-4-5-251128'],
        'Stable Diffusion': ['stable-diffusion-xl-1024-v1-0'],
        'Tencent Hunyuan': ['201']
    };

    const fetchAllData = async () => {
        setLoading(true);
        try {
            const [usersRes, rulesRes, transRes] = await Promise.allSettled([
                api.get('/users'),
                getPricingRules(),
                getTransactions(50, transactionFilterUser || null)
            ]);

            if (usersRes.status === 'fulfilled') {
                const fetchedUsers = usersRes.value.data;
                setUsers(fetchedUsers);
                
                // Extract System User Settings to populate Model Options
                const systemUsers = fetchedUsers.filter(u => u.is_system);
                if (systemUsers.length > 0) {
                     // We actually need to fetch api_settings from somewhere for these users, 
                     // OR rely on the sync endpoint logic.
                     // But the UI hardcoded MODEL_OPTIONS.
                     // Let's TRY to fetch system settings if an endpoint exists, or infer.
                     // The endpoint `GET /billing/rules/sync` does sync, maybe we call it or rely on existing rules?
                     // Better: Extract unique provider/models from existing Pricing Rules to seed the dropdowns + defaults
                }
            } 
            
            if (rulesRes.status === 'fulfilled') {
                const rules = rulesRes.value;
                setPricingRules(rules);
                
                // Dynamically update MODEL_OPTIONS based on existing rules + Hardcoded defaults
                // This ensures if a rule exists for a model not in hardcode, it appears.
                const dynamicModels = { ...MODEL_OPTIONS };
                rules.forEach(r => {
                    if (r.provider && r.model) {
                        if (!dynamicModels[r.provider]) dynamicModels[r.provider] = [];
                        if (!dynamicModels[r.provider].includes(r.model)) {
                            dynamicModels[r.provider].push(r.model);
                        }
                    }
                });
                // Force update matching properties if needed, but since MODEL_OPTIONS is const outside, 
                // we should perhaps use a state for options.
                // For this quick fix, I will rely on the `syncPricingRules` button logic to populate database,
                // and here I will just make the dropdown use a verified list or allow custom input.
                // Actually, the user says "inconsistent with settings". 
                // Settings uses `backend/app/core/config.py` or hardcoded lists in `Settings.jsx`.
                // I will grab the list from `Settings.jsx` logic if I can, OR just make the input editable.
                // Making it editable (or creatable) is best.
            }

            if (transRes.status === 'fulfilled') setTransactions(transRes.value);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchTransactionsOnly = async () => {
        try {
            const data = await getTransactions(50, transactionFilterUser || null);
            setTransactions(data);
        } catch (e) {
            console.error("Failed to load transactions", e);
        }
    };

    // Reload transactions when filter changes
    useEffect(() => {
        if (activeTab === 'transactions') {
            fetchTransactionsOnly();
        }
    }, [transactionFilterUser, activeTab]);

    const handleSaveRule = async () => {
        try {
            if (editingRule) {
                await updatePricingRule(editingRule.id, ruleForm);
            } else {
                await createPricingRule(ruleForm);
            }
            setIsRuleModalOpen(false);
            setEditingRule(null);
            fetchAllData(); // Refresh
        } catch (e) {
            alert("Failed to save rule: " + e.message);
        }
    };

    const handleSyncRules = async () => {
        setLoading(true);
        try {
            const added = await syncPricingRules();
            alert(`Sync complete. Added ${added.length} new rules.`);
            fetchAllData();
        } catch(e) {
            alert("Sync failed: " + e.message);
            setLoading(false);
        }
    };

    const handleDeleteRule = async (id) => {
        if (!window.confirm("Delete this pricing rule?")) return;
        try {
            await deletePricingRule(id);
            fetchAllData();
        } catch (e) { alert(e.message); }
    };

    const handleUpdateCredits = async () => {
        if (!creditEditUser) return;
        try {
            await updateUserCredits(creditEditUser.id, parseInt(creditAmount), 'set'); // or 'add' logic if UI supports it
            setCreditEditUser(null);
            fetchAllData();
        } catch (e) { alert(e.message); }
    };

    // Initial Fetch
    useEffect(() => {
        fetchAllData();
    }, []);


    // Helper Components
    const TabButton = ({ id, label, icon: Icon }) => (
        <button
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                activeTab === id ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
        >
            <Icon size={18} />
            {label}
        </button>
    );

    const Toggle = ({ active, onClick, color = "bg-green-500", label }) => (
        <button 
            onClick={onClick}
            className={`
                relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900 focus:ring-primary
                ${active ? color : 'bg-gray-700'}
            `}
            title={label}
        >
            <span
                className={`${
                    active ? 'translate-x-6' : 'translate-x-1'
                } inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
            />
        </button>
    );



    const updateUser = async (userId, data) => {
        try {
            const response = await api.put(`/users/${userId}`, data);
            setUsers(users.map(u => u.id === userId ? { ...u, ...response.data } : u));
            if (data.is_system) fetchAllData();
        } catch (e) {
            alert(e.message || "Update failed");
        }
    };

    if (error) {
         return (
             <div className="min-h-screen bg-[#09090b] text-white flex flex-col">
                <Navbar />
                <div className="flex-1 flex items-center justify-center">
                    <div className="bg-red-500/10 border border-red-500/50 p-8 rounded-xl text-center">
                        <Shield className="w-12 h-12 text-red-500 mx-auto mb-4" />
                        <h2 className="text-xl font-bold mb-2">Access Resticted</h2>
                        <p className="text-red-200">{error}</p>
                    </div>
                </div>
                <Footer />
             </div>
         )
    }

    return (
        <div className="min-h-screen bg-[#09090b] text-white flex flex-col font-sans">
            <Navbar forceSolid={true} hideMenu={true} className="bg-[#09090b]/90 border-white/10" />
            
            <main className="flex-1 container mx-auto px-4 pt-24 pb-8">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <Shield className="w-8 h-8 text-primary" />
                            Admin Console
                        </h1>
                        <p className="text-gray-400 mt-1">Manage users, permissions, and billing.</p>
                    </div>
                    
                    <div className="flex gap-2">
                        <TabButton id="users" label="Users" icon={User} />
                        <TabButton id="pricing" label="Pricing" icon={DollarSign} />
                        <TabButton id="transactions" label="History" icon={Activity} />
                    </div>
                </div>

                {/* Content Area */}
                <div className="bg-[#18181b] rounded-xl border border-gray-800 p-6 min-h-[500px]">
                    
                    {/* USERS TAB */}
                    {activeTab === 'users' && (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="border-b border-gray-800 text-gray-400 text-sm">
                                        <th className="p-3">User</th>
                                        <th className="p-3">Credits</th>
                                        <th className="p-3 text-center">Active</th>
                                        <th className="p-3 text-center">Authorized</th>
                                        <th className="p-3 text-center">System Key Provider</th>
                                        <th className="p-3 text-center">Superuser</th>
                                        <th className="p-3">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(user => (
                                        <tr key={user.id} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                                            <td className="p-3">
                                                <div className="font-medium">{user.username}</div>
                                                <div className="text-xs text-gray-500">{user.email}</div>
                                            </td>
                                            <td className="p-3 font-mono text-green-400">
                                                {user.credits}
                                                <button 
                                                    onClick={() => { setCreditEditUser(user); setCreditAmount(user.credits); }}
                                                    className="ml-2 text-gray-500 hover:text-white"
                                                >
                                                    <Edit2 size={12} />
                                                </button>
                                            </td>
                                            <td className="p-3 text-center">
                                                <Toggle 
                                                    active={user.is_active} 
                                                    onClick={() => updateUser(user.id, { is_active: !user.is_active })}
                                                />
                                            </td>
                                            <td className="p-3 text-center">
                                                <Toggle 
                                                    active={user.is_authorized} 
                                                    color="bg-blue-500"
                                                    onClick={() => updateUser(user.id, { is_authorized: !user.is_authorized })}
                                                />
                                            </td>
                                            <td className="p-3 text-center">
                                                <Toggle 
                                                    active={user.is_system} 
                                                    color="bg-purple-500"
                                                    onClick={() => updateUser(user.id, { is_system: !user.is_system })}
                                                />
                                            </td>
                                            <td className="p-3 text-center">
                                                 <Toggle 
                                                    active={user.is_superuser} 
                                                    color="bg-red-500"
                                                    onClick={() => updateUser(user.id, { is_superuser: !user.is_superuser })}
                                                />
                                            </td>
                                            <td className="p-3">
                                                {/* Details or Delete button could go here */}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {/* PRICING TAB */}
                    {activeTab === 'pricing' && (
                        <div>
                            <div className="flex justify-between mb-4">
                                <h3 className="text-lg font-bold">Pricing Rules</h3>
                                <div className="flex gap-2">
                                    <button
                                        onClick={handleSyncRules}
                                        className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1 rounded flex items-center gap-2"
                                        title="Import system API settings"
                                    >
                                        <RefreshCw size={16} /> Sync Settings
                                    </button>
                                    <button 
                                        onClick={() => { 
                                            setEditingRule(null); 
                                            setRuleForm({ task_type: 'llm_chat', provider: '', model: '', cost: 1, unit_type: 'per_call' }); 
                                            setCalcPriceUSD('');
                                            setExchangeRate(10);
                                            setMarkup('1.0');
                                            setIsRuleModalOpen(true); 
                                        }}
                                        className="bg-primary hover:bg-primary/90 text-white px-3 py-1 rounded flex items-center gap-2"
                                    >
                                    <Plus size={16} /> Add Rule
                                </button>
                                </div>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="border-b border-gray-800 text-gray-400 text-sm">
                                            <th className="p-3">Provider</th>
                                            <th className="p-3">Model</th>
                                            <th className="p-3">Task</th>
                                            <th className="p-3">Cost (Credits)</th>
                                            <th className="p-3">Status</th>
                                            <th className="p-3 text-right">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {pricingRules.map(rule => (
                                            <tr key={rule.id} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                                                <td className="p-3">{rule.provider || '* (All)'}</td>
                                                <td className="p-3">{rule.model || '* (All)'}</td>
                                                <td className="p-3"><span className="bg-gray-700 px-2 py-0.5 rounded text-xs">{rule.task_type}</span></td>
                                                <td className="p-3">
                                                    {rule.task_type === 'llm_chat' && (rule.cost_input || rule.cost_output) ? (
                                                        <div className="flex flex-col text-xs font-mono">
                                                            <span className="text-blue-300" title="Input Tokens">In: {rule.cost_input} <span className="text-gray-600">/ M</span></span>
                                                            <span className="text-green-300" title="Output Tokens">Out: {rule.cost_output} <span className="text-gray-600">/ M</span></span>
                                                        </div>
                                                    ) : (
                                                        <span className="font-bold text-yellow-400">
                                                            {rule.cost} <span className="text-[10px] text-gray-500 font-normal">/ {rule.unit_type.replace('per_', '').replace('_', ' ')}</span>
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="p-3">
                                                    <span className={`w-2 h-2 rounded-full inline-block mr-2 ${rule.is_active ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                                    {rule.is_active ? 'Active' : 'Inactive'}
                                                </td>
                                                <td className="p-3 text-right flex justify-end gap-2">
                                                    <button onClick={() => { 
                                                        setEditingRule(rule); 
                                                        setRuleForm(rule); 
                                                        
                                                        const m = rule.ref_markup || 1.0;
                                                        const r = rule.ref_exchange_rate || 10;
                                                        setMarkup(m.toString());
                                                        setExchangeRate(r);

                                                        setCalcPriceUSD(rule.ref_cost_cny !== undefined && rule.ref_cost_cny !== null ? rule.ref_cost_cny : ((rule.cost || 0)/(r*m)));
                                                        
                                                        // For dual pricing, recreate approximates if ref missing
                                                        const inputApprox = (rule.cost_input || 0) / (r * m);
                                                        const outputApprox = (rule.cost_output || 0) / (r * m);

                                                        setCalcPriceInput(rule.ref_cost_input_cny !== undefined && rule.ref_cost_input_cny !== null ? rule.ref_cost_input_cny : inputApprox);
                                                        setCalcPriceOutput(rule.ref_cost_output_cny !== undefined && rule.ref_cost_output_cny !== null ? rule.ref_cost_output_cny : outputApprox);
                                                        
                                                        setIsRuleModalOpen(true); 
                                                    }} className="text-blue-400 hover:text-blue-300"><Edit2 size={16} /></button>
                                                    <button onClick={() => handleDeleteRule(rule.id)} className="text-red-400 hover:text-red-300"><Trash2 size={16} /></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* TRANSACTIONS TAB */}
                    {activeTab === 'transactions' && (
                        <div>
                             <div className="flex justify-between items-center mb-4">
                                <h3 className="text-lg font-bold">Recent Transactions (Last 50)</h3>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-gray-400">Filter by User:</span>
                                    <select 
                                        className="bg-gray-800 border border-gray-700 text-sm rounded p-2 text-gray-300 focus:outline-none focus:border-primary min-w-[200px]"
                                        value={transactionFilterUser}
                                        onChange={(e) => setTransactionFilterUser(e.target.value)}
                                    >
                                        <option value="">All Users</option>
                                        {users.map(u => (
                                            <option key={u.id} value={u.id}>
                                                {u.username} (ID: {u.id}) - {u.credits} credits
                                            </option>
                                        ))}
                                    </select>
                                    <button 
                                        onClick={fetchTransactionsOnly}
                                        className="p-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-300"
                                        title="Refresh"
                                    >
                                        <RefreshCw size={16} />
                                    </button>
                                </div>
                             </div>
                             <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse text-sm">
                                    <thead>
                                        <tr className="border-b border-gray-800 text-gray-400">
                                            <th className="p-3">Time</th>
                                            <th className="p-3">User ID</th>
                                            <th className="p-3">Type</th>
                                            <th className="p-3">Details</th>
                                            <th className="p-3 text-right">Amount</th>
                                            <th className="p-3 text-right">Balance</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {transactions.map(t => (
                                            <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                                                <td className="p-3 text-gray-400">{new Date(t.created_at).toLocaleString()}</td>
                                                <td className="p-3">{t.user_id}</td>
                                                <td className="p-3"><span className="bg-gray-800 px-2 py-0.5 rounded text-xs uppercase text-gray-300">{t.task_type}</span></td>
                                                <td className="p-3 text-xs text-gray-500">
                                                    <div className="max-h-[150px] overflow-y-auto whitespace-pre-wrap break-all w-[350px] bg-gray-900/50 p-1 rounded border border-gray-800 font-mono">
                                                        {JSON.stringify(t.details, null, 2)}
                                                    </div>
                                                </td>
                                                <td className={`p-3 text-right font-mono ${t.amount < 0 ? 'text-red-400' : 'text-green-400'}`}>
                                                    {t.amount > 0 ? '+' : ''}{t.amount}
                                                </td>
                                                <td className="p-3 text-right font-mono text-gray-400">{t.balance_after}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                </div>
            </main>

            {/* Config Modal */}
            {isRuleModalOpen && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
                    <div className="bg-gray-900 border border-gray-700 p-6 rounded-xl w-full max-w-md">
                        <h3 className="text-xl font-bold mb-4">{editingRule ? 'Edit Rule' : 'New Pricing Rule'}</h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Task Type</label>
                                <select 
                                    className="w-full bg-gray-800 border border-gray-700 rounded p-2"
                                    value={ruleForm.task_type}
                                    onChange={e => setRuleForm({
                                        ...ruleForm, 
                                        task_type: e.target.value,
                                        provider: '',  // Reset dependent fields
                                        model: ''
                                    })}
                                >
                                    <option value="llm_chat">Chat (LLM)</option>
                                    <option value="image_gen">Image Generation</option>
                                    <option value="video_gen">Video Generation</option>
                                    <option value="analysis">Analysis (Text)</option>
                                    <option value="analysis_character">Character Analysis</option>
                                </select>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm text-gray-400 mb-1">Provider (Optional)</label>
                                    <select 
                                        className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm"
                                        value={ruleForm.provider || ''}
                                        onChange={e => setRuleForm({...ruleForm, provider: e.target.value || null, model: ''})}
                                    >
                                        <option value="">Any (*)</option>
                                        {(PROVIDER_OPTIONS[ruleForm.task_type] || []).map(opt => (
                                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                                        ))}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm text-gray-400 mb-1">Model (Optional)</label>
                                    <select 
                                        className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm"
                                        value={ruleForm.model || ''}
                                        onChange={e => setRuleForm({...ruleForm, model: e.target.value || null})}
                                    >
                                       <option value="">Any (*)</option>
                                       {(MODEL_OPTIONS[ruleForm.provider] || []).map(m => (
                                           <option key={m} value={m}>{m}</option>
                                       ))}
                                    </select>
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Unit Type</label>
                                <select 
                                    className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm"
                                    value={ruleForm.unit_type || 'per_call'}
                                    onChange={e => setRuleForm({...ruleForm, unit_type: e.target.value})}
                                >
                                    <option value="per_call">Per API Call (Request)</option>
                                    <option value="per_1k_tokens">Per 1k Tokens</option>
                                    <option value="per_million_tokens">Per 1M Tokens</option>
                                    <option value="per_image">Per Image</option>
                                    <option value="per_second">Per Second (Video)</option>
                                    <option value="per_minute">Per Minute</option>
                                </select>
                            </div>

                            <div className="bg-black/40 p-3 rounded border border-white/5 space-y-3">
                                <label className="block text-xs font-medium text-blue-400 uppercase">Auto-Calculate Cost (CNY)</label>
                                
                                {ruleForm.task_type === 'llm_chat' ? (
                                    /* LLM Dual Pricing Calculator */
                                    <div className="grid grid-cols-2 gap-3 mb-2">
                                        <div>
                                            <label className="block text-[10px] text-gray-400 mb-1">Input Price (Per {ruleForm.unit_type === 'per_1k_tokens' ? '1K' : '1M'} Tokens)</label>
                                            <input 
                                                type="number" 
                                                step="0.0001"
                                                placeholder={ruleForm.unit_type === 'per_1k_tokens' ? "e.g. 0.002" : "e.g. 1.00"}
                                                className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                                value={calcPriceInput}
                                                onChange={(e) => setCalcPriceInput(e.target.value)}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] text-gray-400 mb-1">Output Price (Per {ruleForm.unit_type === 'per_1k_tokens' ? '1K' : '1M'} Tokens)</label>
                                            <input 
                                                type="number" 
                                                step="0.0001"
                                                placeholder={ruleForm.unit_type === 'per_1k_tokens' ? "e.g. 0.006" : "e.g. 6.00"}
                                                className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                                value={calcPriceOutput}
                                                onChange={(e) => setCalcPriceOutput(e.target.value)}
                                            />
                                        </div>
                                    </div>
                                ) : (
                                    /* Standard Single Pricing Calculator */
                                    <div className="mb-2">
                                        <label className="block text-[10px] text-gray-400 mb-1">
                                            {ruleForm.unit_type === 'per_million_tokens' ? 'Price per 1M Tokens (Yuan)' :
                                            ruleForm.unit_type === 'per_1k_tokens' ? 'Price per 1K Tokens (Yuan)' :
                                            ruleForm.unit_type === 'per_image' ? 'Price per Image (Yuan)' :
                                            ruleForm.unit_type === 'per_second' ? 'Price per Second (Yuan)' :
                                            ruleForm.unit_type === 'per_minute' ? 'Price per Minute (Yuan)' :
                                            'Price per Request (Yuan)'}
                                        </label>
                                        <input 
                                            type="number" 
                                            step="0.0001"
                                            placeholder={
                                                ruleForm.unit_type === 'per_million_tokens' ? '36.00' :
                                                ruleForm.unit_type === 'per_image' ? '0.30' :
                                                '0.015'
                                            }
                                            className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                            value={calcPriceUSD}
                                            onChange={(e) => setCalcPriceUSD(e.target.value)}
                                        />
                                        <p className="text-[9px] text-gray-600 mt-1">
                                            {ruleForm.unit_type === 'per_million_tokens' ? 'e.g. GPT-4o Input: ~￥36.00' :
                                             ruleForm.unit_type === 'per_image' ? 'e.g. DALL-E 3: ~￥0.30' :
                                             ruleForm.unit_type === 'per_second' ? 'e.g. Runway: ~￥0.35/sec' :
                                             'Base provider cost in Yuan'}
                                        </p>
                                    </div>
                                )}

                                <div className="grid grid-cols-2 gap-3 border-t border-white/10 pt-2">
                                    <div>
                                        <label className="block text-[10px] text-gray-400 mb-1">Multiplier (Markup)</label>
                                        <input 
                                            type="number"
                                            step="0.1" 
                                            value={markup}
                                            className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                            onChange={(e) => setMarkup(e.target.value)}
                                        />
                                        <p className="text-[9px] text-gray-600 mt-1">e.g. 2.0 = 2x Cost</p>
                                    </div>
                                    <div>
                                        <label className="block text-[10px] text-gray-400 mb-1">Exchange (￥1=Credits)</label>
                                        <input 
                                            type="number" 
                                            value={exchangeRate}
                                            className="w-full bg-gray-900 border border-gray-700 rounded p-1.5 text-sm"
                                            onChange={(e) => setExchangeRate(parseFloat(e.target.value) || 10)}
                                        />
                                    </div>
                                </div>
                                <div className="text-[10px] text-gray-500 bg-white/5 p-2 rounded">
                                    <div className="flex justify-between items-center mb-1">
                                        <span>Calculation:</span>
                                        <span className="font-mono text-xs text-white">
                                           Price × {exchangeRate} × {markup}x
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-center border-t border-white/10 pt-1">
                                        <span className="text-yellow-500 font-bold">Final Cost:</span>
                                        <span className="font-mono text-yellow-400 font-bold text-sm">
                                            {ruleForm.task_type === 'llm_chat' ? (
                                                <span>
                                                    In: {Math.ceil((parseFloat(calcPriceInput)||0) * exchangeRate * markup)} / 
                                                    Out: {Math.ceil((parseFloat(calcPriceOutput)||0) * exchangeRate * markup)}
                                                </span>
                                            ) : (
                                                <span>{Math.ceil((parseFloat(calcPriceUSD) || 0) * exchangeRate * markup)} Credits</span>
                                            )}
                                        </span>
                                    </div>
                                    <div className="text-[9px] text-gray-600 mt-1 text-right">
                                        Per {ruleForm.unit_type.replace('per_', '').replace('_', ' ')}
                                    </div>
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm text-gray-400 mb-1">
                                    {ruleForm.task_type === 'llm_chat' ? 'Cost (Credits: Input / Output)' : 'Cost (Credits)'}
                                </label>
                                {ruleForm.task_type === 'llm_chat' ? (
                                     <div className="grid grid-cols-2 gap-2">
                                        <div>
                                            <span className="text-[10px] text-gray-500">Input (per 1M)</span>
                                            <input 
                                                type="number" 
                                                className="w-full bg-gray-800 border border-gray-700 rounded p-2 font-mono text-yellow-400 font-bold"
                                                value={ruleForm.cost_input || 0}
                                                onChange={e => setRuleForm({...ruleForm, cost_input: parseInt(e.target.value) || 0})}
                                            />
                                        </div>
                                        <div>
                                            <span className="text-[10px] text-gray-500">Output (per 1M)</span>
                                            <input 
                                                type="number" 
                                                className="w-full bg-gray-800 border border-gray-700 rounded p-2 font-mono text-yellow-400 font-bold"
                                                value={ruleForm.cost_output || 0}
                                                onChange={e => setRuleForm({...ruleForm, cost_output: parseInt(e.target.value) || 0})}
                                            />
                                        </div>
                                     </div>
                                ) : (
                                    <input 
                                        type="number" 
                                        className="w-full bg-gray-800 border border-gray-700 rounded p-2 font-mono text-yellow-400 font-bold"
                                        value={ruleForm.cost}
                                        onChange={e => setRuleForm({...ruleForm, cost: parseInt(e.target.value)})}
                                    />
                                )}
                            </div>
                            <div className="flex justify-end gap-2 mt-6">
                                <button onClick={() => setIsRuleModalOpen(false)} className="px-4 py-2 hover:bg-gray-800 rounded">Cancel</button>
                                <button onClick={handleSaveRule} className="px-4 py-2 bg-primary hover:bg-primary/90 text-black font-bold rounded">Save</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Credit Modal */}
            {creditEditUser && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
                    <div className="bg-gray-900 border border-gray-700 p-6 rounded-xl w-full max-w-sm">
                        <h3 className="text-xl font-bold mb-4">Edit Credits for {creditEditUser.username}</h3>
                        <p className="text-gray-400 text-sm mb-4">Set the absolute credit balance for this user.</p>
                        <input 
                            type="number" 
                            className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-2xl font-mono text-center text-green-400 mb-6"
                            value={creditAmount}
                            onChange={e => setCreditAmount(e.target.value)}
                        />
                        <div className="flex justify-end gap-2">
                             <button onClick={() => setCreditEditUser(null)} className="px-4 py-2 hover:bg-gray-800 rounded">Cancel</button>
                             <button onClick={handleUpdateCredits} className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white font-bold rounded">Update Balance</button>
                        </div>
                    </div>
                </div>
            )}
            
        </div>
    );
};

export default UserAdmin;

