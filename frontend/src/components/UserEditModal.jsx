import React from 'react';
import { getUiLang, tUI } from '../lib/uiLang';

const UserEditModal = ({
    draft,
    setDraft,
    onClose,
    onSave,
    isSaving,
    normalizeUserActiveLevel,
    isUserEnabled,
}) => {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);

    if (!draft) {
        return null;
    }

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50" onClick={onClose}>
            <div className="bg-gray-900 border border-gray-700 p-6 rounded-xl w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
                <h3 className="text-xl font-bold mb-4">{t('编辑用户', 'Edit User')} #{draft.id}</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <input className="bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm" value={draft.username} placeholder={t('用户名', 'Username')} onChange={(e) => setDraft((prev) => ({ ...prev, username: e.target.value }))} />
                    <input className="bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm" value={draft.email} placeholder={t('邮箱', 'Email')} onChange={(e) => setDraft((prev) => ({ ...prev, email: e.target.value }))} />
                    <input className="md:col-span-2 bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm" value={draft.full_name} placeholder={t('姓名', 'Full Name')} onChange={(e) => setDraft((prev) => ({ ...prev, full_name: e.target.value }))} />
                    <input className="bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm" inputMode="numeric" value={normalizeUserActiveLevel(draft.is_active, 1)} placeholder={t('启用级别', 'Active Level')} onChange={(e) => setDraft((prev) => ({ ...prev, is_active: normalizeUserActiveLevel(e.target.value, prev?.is_active ?? 1) }))} />
                    <select className="bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm" value={draft.account_status} onChange={(e) => setDraft((prev) => ({ ...prev, account_status: Number(e.target.value) }))}>
                        <option value={1}>{t('正常', 'Active')}</option>
                        <option value={0}>{t('禁用', 'Disabled')}</option>
                        <option value={-1}>{t('待邮箱校验', 'Pending Verify')}</option>
                    </select>
                    <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={isUserEnabled(draft.is_active)} onChange={(e) => setDraft((prev) => ({ ...prev, is_active: e.target.checked ? Math.max(1, normalizeUserActiveLevel(prev?.is_active, 1)) : 0 }))} />{t('启用', 'Enabled')}</label>
                    <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={!!draft.email_verified} onChange={(e) => setDraft((prev) => ({ ...prev, email_verified: e.target.checked }))} />{t('邮箱已验证', 'Email Verified')}</label>
                    <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={!!draft.is_authorized} onChange={(e) => setDraft((prev) => ({ ...prev, is_authorized: e.target.checked }))} />{t('授权', 'Authorized')}</label>
                    <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={!!draft.is_system} onChange={(e) => setDraft((prev) => ({ ...prev, is_system: e.target.checked }))} />{t('系统密钥提供方', 'System Key Provider')}</label>
                    <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={!!draft.is_superuser} onChange={(e) => setDraft((prev) => ({ ...prev, is_superuser: e.target.checked }))} />{t('超级管理员', 'Superuser')}</label>
                </div>
                <div className="mt-6 flex justify-end gap-2">
                    <button onClick={onClose} className="px-4 py-2 hover:bg-gray-800 rounded">{t('取消', 'Cancel')}</button>
                    <button onClick={onSave} disabled={isSaving} className="px-4 py-2 bg-primary hover:bg-primary/90 text-white font-bold rounded disabled:opacity-50">{isSaving ? t('保存中...', 'Saving...') : t('保存', 'Save')}</button>
                </div>
            </div>
        </div>
    );
};

export default UserEditModal;