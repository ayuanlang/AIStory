import re

with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

find_blk = """                    {showRecharge && (
                        <RechargeModal 
                            onClose={() => setShowRecharge(false)} 
                            onSuccess={() => {
                                refreshBilling();
                                showNotification(t('充值成功！', 'Recharge successful!'), "success");
                            }}
                        />                                
                    )}"""

repl_blk = """                    {showRecharge && (
                        <RechargeModal 
                            onClose={() => {
                                setShowRecharge(false);
                                setRechargeTargetGroupId(null);
                                setRechargeTargetGroupName('');
                            }} 
                            onSuccess={() => {
                                refreshBilling();
                                fetchGroups().then(data => setUserGroups(data)).catch(console.error);
                                showNotification(t('充值成功！', 'Recharge successful!'), "success");
                            }}
                            groupId={rechargeTargetGroupId}
                            groupName={rechargeTargetGroupName}
                        />                                
                    )}"""

# If text exact match fails due to t('...', '...') encoding or line endings, let's use regex
if "groupId={rechargeTargetGroupId}" not in text:
    text = re.sub(
        r'\{showRecharge && \(\s*<RechargeModal \s*onClose=\{\(\) => setShowRecharge\(false\)\}\s*onSuccess=\{\(\) => \{\s*refreshBilling\(\);\s*showNotification\([^)]+\);\s*\}\}\s*/>\s*\)\}',
        repl_blk.strip(),
        text,
        flags=re.DOTALL
    )
    with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Patched RechargeModal hook!")
else:
    print("Already patched.")