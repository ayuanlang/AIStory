import re

with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. State for Group Recharge
state_find = """    const [userGroups, setUserGroups] = useState([]);"""
state_repl = """    const [userGroups, setUserGroups] = useState([]);
    const [rechargeTargetGroupId, setRechargeTargetGroupId] = useState(null);
    const [rechargeTargetGroupName, setRechargeTargetGroupName] = useState('');"""
if 'setRechargeTargetGroupId' not in text:
    text = text.replace(state_find, state_repl)

# 2. Table Row logic for Recharge
row_find = """                                                    {g.permission_level === 2 && (
                                                        <button 
                                                            onClick={() => setAddingMemberToGroupId(g.group_id)}
                                                            className="text-xs px-3 py-1 bg-white/5 hover:bg-white/10 text-white rounded transition-colors"
                                                        >
                                                            {t('+ 添加成员', '+ Member')}
                                                        </button>
                                                    )}
                                                </td>"""

row_repl = """                                                    {g.permission_level === 2 && (
                                                        <div className="flex items-center justify-end gap-2">
                                                            <button 
                                                                onClick={() => setAddingMemberToGroupId(g.group_id)}
                                                                className="text-xs px-3 py-1 bg-white/5 hover:bg-white/10 text-white rounded transition-colors"
                                                            >
                                                                {t('+ 添加成员', '+ Member')}
                                                            </button>
                                                            <button 
                                                                onClick={() => {
                                                                    setRechargeTargetGroupId(g.group_id);
                                                                    setRechargeTargetGroupName(g.name);
                                                                    setShowRecharge(true);
                                                                }}
                                                                className="text-xs px-3 py-1 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-400 rounded transition-colors flex items-center gap-1"
                                                            >
                                                                <Coins className="w-3 h-3" /> {t('充值', 'Top-up')}
                                                            </button>
                                                        </div>
                                                    )}
                                                </td>"""
text = text.replace(row_find, row_repl)

# Fallback regex if mismatch
if 'setRechargeTargetGroupId(g.group_id)' not in text:
    text = re.sub(r'\{g\.permission_level\s*===\s*2\s*&&\s*\(\s*<button.*?onClick=\{\(\)\s*=>\s*setAddingMemberToGroupId\(g\.group_id\)\}.*?</button>\s*\)\}', row_repl.replace('<td', '').replace('</td>', '').strip()[:-5], text, flags=re.DOTALL)

# 3. Mount RechargeModal for group
modal_find = """{showRecharge && <RechargeModal onClose={() => setShowRecharge(false)} onSuccess={refreshBilling} />}"""
modal_repl = """{showRecharge && (
                <RechargeModal 
                    onClose={() => {
                        setShowRecharge(false);
                        setRechargeTargetGroupId(null);
                        setRechargeTargetGroupName('');
                    }} 
                    onSuccess={() => {
                        refreshBilling();
                        fetchGroups().then(data => setUserGroups(data)).catch(console.error);
                    }} 
                    groupId={rechargeTargetGroupId}
                    groupName={rechargeTargetGroupName}
                />
            )}"""
if 'groupId={rechargeTargetGroupId}' not in text:
    text = text.replace(modal_find, modal_repl)

with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
print("Settings patched!")