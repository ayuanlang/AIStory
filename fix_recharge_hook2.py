import re

with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

find = """                    {showRecharge && (
                        <RechargeModal 
                            onClose={() => setShowRecharge(false)} 
                            onSuccess={() => {
                                refreshBilling();
                                showNotification(t('充值成功！', 'Recharge successful!'), "success");
                            }}
                        />                                
                    )}"""

repl = """                    {showRecharge && (
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

text_utf8 = text.replace(find, repl)
flag = False

if text != text_utf8:
    text = text_utf8
    flag = True
else:
    # use pure regex ignoring inside space
    part1_re = r'\{showRecharge && \(\s*<RechargeModal\s*onClose=\{\(\)\s*=>\s*setShowRecharge\(false\)\}\s*onSuccess=\{\(\)\s*=>\s*\{[^\}]+\}\}\s*/>\s*\)\}'
    part1_matches = re.findall(part1_re, text)
    if part1_matches:
        text = text.replace(part1_matches[0], repl)
        flag = True


with open(r'c:\AS\AIStory\frontend\src\pages\Settings.jsx', 'w', encoding='utf-8') as f:
    f.write(text)

if flag:
    print("RechargeModal hook successfully patched.")
else:
    print("RechargeModal hook pattern could not be found.")