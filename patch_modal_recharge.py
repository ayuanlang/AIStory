import re

with open(r'c:\AS\AIStory\frontend\src\components\RechargeModal.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Update signature
text = text.replace("const RechargeModal = ({ onClose, onSuccess }) => {", "const RechargeModal = ({ onClose, onSuccess, groupId, groupName }) => {")

# Update create API call
api_find = """            const res = await api.post('/billing/recharge/create', { amount: finalAmount });"""
api_repl = """            const payload = { amount: finalAmount };
            if (groupId) { payload.group_id = groupId; }
            const res = await api.post('/billing/recharge/create', payload);"""
if "payload.group_id" not in text:
    text = text.replace(api_find, api_repl)

# Update Title visually
title_find = """              <div className="bg-zinc-900 border border-white/10 p-6 rounded-xl w-full max-w-md shadow-2xl relative">"""
title_repl = """              <div className="bg-zinc-900 border border-white/10 p-6 rounded-xl w-full max-w-md shadow-2xl relative">
                  {groupId && (
                      <div className="bg-yellow-500/10 border border-yellow-500/20 text-yellow-500 text-xs px-3 py-2 rounded-md mb-4 flex items-center justify-between">
                          <span>{t(`正在为团队充值: ${groupName}`, `Topping up for group: ${groupName}`)}</span>
                          <span className="font-bold">{t('支持企业对公开票', 'Supports Biz Invoice')}</span>
                      </div>
                  )}"""
if "正在为团队充值" not in text:
    text = text.replace(title_find, title_repl)

with open(r'c:\AS\AIStory\frontend\src\components\RechargeModal.jsx', 'w', encoding='utf-8') as f:
    f.write(text)
print("RechargeModal patched!")