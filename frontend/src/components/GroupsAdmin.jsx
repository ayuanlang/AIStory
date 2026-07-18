import React, { useEffect, useState } from 'react';
import { Edit2, RefreshCw, Trash2, Users } from 'lucide-react';
import {
    getAdminGroupsPage,
    updateAdminGroup,
    updateAdminGroupCredits,
    deleteAdminGroup,
    fetchGroupMembers,
    addGroupMember,
    updateGroupMember,
    removeGroupMember,
} from '../services/api';
import GroupCreditAllocatePanel from './GroupCreditAllocatePanel';
import { getUiLang, tUI } from '../lib/uiLang';
import { confirmUiMessage } from '../lib/uiMessage';

export default function GroupsAdmin() {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);

    const [groups, setGroups] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(20);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const [creditEditGroup, setCreditEditGroup] = useState(null);
    const [creditAmount, setCreditAmount] = useState(0);

    const [viewingGroup, setViewingGroup] = useState(null);
    const [members, setMembers] = useState([]);
    const [loadingMembers, setLoadingMembers] = useState(false);

    const [addingToGroup, setAddingToGroup] = useState(null);
    const [newMemberInput, setNewMemberInput] = useState('');

    const totalPages = Math.max(1, Math.ceil((total || 0) / (pageSize || 20)));

    const fetchGroups = async (nextPage = page, nextPageSize = pageSize) => {
        setLoading(true);
        setError('');
        try {
            const res = await getAdminGroupsPage(nextPage, nextPageSize);
            setGroups(Array.isArray(res?.items) ? res.items : []);
            setTotal(Number(res?.total || 0));
            setPage(Number(res?.page || nextPage));
            setPageSize(Number(res?.page_size || nextPageSize));
        } catch (e) {
            console.error(e);
            setError(e?.response?.data?.detail || e?.message || t('加载失败', 'Load failed'));
            setGroups([]);
            setTotal(0);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchGroups(page, pageSize);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page, pageSize]);

    const patchGroupLocal = (groupId, patch) => {
        setGroups((prev) => prev.map((g) => (g.id === groupId ? { ...g, ...patch } : g)));
        if (viewingGroup?.id === groupId) {
            setViewingGroup((prev) => (prev ? { ...prev, ...patch } : prev));
        }
    };

    const saveGroupField = async (groupId, data) => {
        try {
            const updated = await updateAdminGroup(groupId, data);
            patchGroupLocal(groupId, updated);
        } catch (e) {
            console.error(e);
            alert(e?.response?.data?.detail || e?.message || t('更新失败', 'Update failed'));
            fetchGroups(page, pageSize);
        }
    };

    const handleSaveCredits = async () => {
        if (!creditEditGroup) return;
        try {
            const res = await updateAdminGroupCredits(creditEditGroup.id, Number(creditAmount || 0), 'set');
            patchGroupLocal(creditEditGroup.id, { credits: res?.credits ?? Number(creditAmount || 0) });
            setCreditEditGroup(null);
        } catch (e) {
            console.error(e);
            alert(e?.response?.data?.detail || e?.message || t('积分更新失败', 'Credit update failed'));
        }
    };

    const handleDeleteGroup = async (group) => {
        const ok = await confirmUiMessage(
            t(`确认删除用户组「${group.name}」？此操作不可恢复。`, `Delete group "${group.name}"? This cannot be undone.`)
        );
        if (!ok) return;
        try {
            await deleteAdminGroup(group.id);
            if (viewingGroup?.id === group.id) {
                setViewingGroup(null);
                setMembers([]);
            }
            await fetchGroups(page, pageSize);
        } catch (e) {
            console.error(e);
            alert(e?.response?.data?.detail || e?.message || t('删除失败', 'Delete failed'));
        }
    };

    const openMembers = async (group) => {
        setViewingGroup(group);
        setMembers([]);
        setLoadingMembers(true);
        try {
            const list = await fetchGroupMembers(group.id);
            setMembers(Array.isArray(list) ? list : []);
        } catch (e) {
            console.error(e);
            setMembers([]);
            alert(e?.response?.data?.detail || e?.message || t('加载成员失败', 'Failed to load members'));
        } finally {
            setLoadingMembers(false);
        }
    };

    const refreshMembers = async (groupId) => {
        setLoadingMembers(true);
        try {
            const list = await fetchGroupMembers(groupId);
            setMembers(Array.isArray(list) ? list : []);
            patchGroupLocal(groupId, { member_count: Array.isArray(list) ? list.length : 0 });
        } catch (e) {
            console.error(e);
        } finally {
            setLoadingMembers(false);
        }
    };

    const handleAddMembers = async () => {
        if (!addingToGroup || !newMemberInput.trim()) return;
        const tokens = newMemberInput.split(/[\s,，;；\n]+/).map((u) => u.trim()).filter(Boolean);
        if (tokens.length === 0) return;

        let successCount = 0;
        let failCount = 0;
        for (const token of tokens) {
            try {
                const payload = token.includes('@')
                    ? { email: token, permission_level: 1 }
                    : { username: token, permission_level: 1 };
                await addGroupMember(addingToGroup.id, payload);
                successCount += 1;
            } catch (e) {
                console.error(e);
                failCount += 1;
            }
        }

        setNewMemberInput('');
        const groupId = addingToGroup.id;
        setAddingToGroup(null);
        await fetchGroups(page, pageSize);
        if (viewingGroup?.id === groupId) {
            await refreshMembers(groupId);
        }
        if (failCount === 0) {
            alert(t(`成功添加 ${successCount} 个成员`, `Successfully added ${successCount} members`));
        } else {
            alert(t(
                `添加完成。成功: ${successCount}，失败: ${failCount}`,
                `Done. Success: ${successCount}, Failed: ${failCount}`
            ));
        }
    };

    const handleToggleMemberRole = async (member) => {
        if (!viewingGroup) return;
        const nextLevel = member.permission_level >= 2 ? 1 : 2;
        try {
            const updated = await updateGroupMember(viewingGroup.id, member.user_id, {
                permission_level: nextLevel,
            });
            setMembers((prev) => prev.map((m) => (m.user_id === member.user_id ? { ...m, ...updated } : m)));
        } catch (e) {
            console.error(e);
            alert(e?.response?.data?.detail || e?.message || t('更新角色失败', 'Failed to update role'));
        }
    };

    const handleRemoveMember = async (member) => {
        if (!viewingGroup) return;
        const ok = await confirmUiMessage(
            t(`确认将 ${member.username || member.email || member.user_id} 移出该组？`, `Remove ${member.username || member.email || member.user_id} from this group?`)
        );
        if (!ok) return;
        try {
            await removeGroupMember(viewingGroup.id, member.user_id);
            await refreshMembers(viewingGroup.id);
            await fetchGroups(page, pageSize);
        } catch (e) {
            console.error(e);
            alert(e?.response?.data?.detail || e?.message || t('移除失败', 'Remove failed'));
        }
    };

    return (
        <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-sm text-gray-300">
                <div className="flex items-center gap-3">
                    <div>
                        {t('用户组总量', 'Total Groups')}: <span className="font-semibold text-white">{total}</span>
                    </div>
                    <button
                        onClick={() => fetchGroups(page, pageSize)}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-xs"
                        disabled={loading}
                    >
                        <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                        {t('刷新', 'Refresh')}
                    </button>
                </div>
                <div className="flex items-center gap-2">
                    <span>{t('每页', 'Per Page')}</span>
                    <select
                        className="bg-black/30 border border-gray-700 rounded px-2 py-1 text-xs"
                        value={pageSize}
                        onChange={(e) => {
                            setPage(1);
                            setPageSize(Number(e.target.value || 20));
                        }}
                    >
                        {[10, 20, 50, 100].map((size) => (
                            <option key={size} value={size}>{size}</option>
                        ))}
                    </select>
                    <button
                        className="px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-50"
                        disabled={page <= 1}
                        onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                    >
                        {t('上一页', 'Prev')}
                    </button>
                    <span>{page} / {totalPages}</span>
                    <button
                        className="px-2 py-1 rounded bg-white/10 hover:bg-white/20 disabled:opacity-50"
                        disabled={page >= totalPages}
                        onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                    >
                        {t('下一页', 'Next')}
                    </button>
                </div>
            </div>

            {error && (
                <div className="mb-3 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                    {error}
                </div>
            )}

            <div className="md:hidden space-y-3">
                {groups.map((group) => (
                    <div key={`group-card-${group.id}`} className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
                        <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                                <div className="text-sm font-semibold text-white">#{group.id} {group.name}</div>
                                <div className="text-xs text-gray-400 mt-1">
                                    {t('所有者', 'Owner')}: {group.owner_username || group.owner_id || '-'}
                                </div>
                            </div>
                            <button
                                className="text-xs px-2 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-300 shrink-0"
                                onClick={() => handleDeleteGroup(group)}
                            >
                                {t('删除', 'Delete')}
                            </button>
                        </div>
                        <input
                            className="w-full bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm"
                            value={group.name || ''}
                            onChange={(e) => patchGroupLocal(group.id, { name: e.target.value })}
                            onBlur={() => saveGroupField(group.id, { name: group.name })}
                        />
                        <textarea
                            rows={2}
                            className="w-full bg-black/30 border border-gray-700 rounded px-3 py-2 text-sm text-gray-300 resize-y"
                            placeholder={t('描述（可选）', 'Description (optional)')}
                            value={group.description || ''}
                            onChange={(e) => patchGroupLocal(group.id, { description: e.target.value })}
                            onBlur={() => saveGroupField(group.id, { description: group.description || '' })}
                        />
                        <div className="grid grid-cols-2 gap-3 text-sm">
                            <div className="rounded-lg bg-black/20 border border-white/5 px-3 py-2">
                                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('成员数', 'Members')}</div>
                                <div className="font-mono">{group.member_count ?? 0}</div>
                            </div>
                            <div className="rounded-lg bg-black/20 border border-white/5 px-3 py-2">
                                <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">{t('积分', 'Credits')}</div>
                                <button
                                    onClick={() => { setCreditEditGroup(group); setCreditAmount(group.credits || 0); }}
                                    className="inline-flex items-center gap-2 text-green-400 font-mono"
                                >
                                    {group.credits ?? 0}
                                    <Edit2 size={12} />
                                </button>
                            </div>
                        </div>
                        <label className="flex items-center justify-between gap-3 rounded-lg bg-black/20 border border-white/5 px-3 py-2 text-sm">
                            <span className="text-gray-300">
                                {t('允许扣组积分', 'Allow group credit billing')}
                            </span>
                            <input
                                type="checkbox"
                                className="h-4 w-4 accent-primary"
                                checked={Boolean(group.allow_group_credit_billing)}
                                onChange={(e) => {
                                    const next = e.target.checked;
                                    patchGroupLocal(group.id, { allow_group_credit_billing: next });
                                    saveGroupField(group.id, { allow_group_credit_billing: next });
                                }}
                            />
                        </label>
                        <div className="flex flex-wrap gap-2">
                            <button
                                onClick={() => openMembers(group)}
                                className="text-xs px-3 py-1.5 rounded bg-white/10 hover:bg-white/20"
                            >
                                {t('查看成员', 'Members')}
                            </button>
                            <button
                                onClick={() => { setAddingToGroup(group); setNewMemberInput(''); }}
                                className="text-xs px-3 py-1.5 rounded bg-white/10 hover:bg-white/20"
                            >
                                {t('+ 添加成员', '+ Member')}
                            </button>
                        </div>
                    </div>
                ))}
                {!loading && groups.length === 0 && (
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-8 text-center text-gray-400">
                        {t('暂无用户组', 'No groups')}
                    </div>
                )}
            </div>

            <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="border-b border-gray-800 text-gray-400 text-sm">
                            <th className="p-3">{t('组ID', 'Group ID')}</th>
                            <th className="p-3">{t('组名', 'Name')}</th>
                            <th className="p-3">{t('描述', 'Description')}</th>
                            <th className="p-3">{t('所有者', 'Owner')}</th>
                            <th className="p-3 text-right">{t('成员数', 'Members')}</th>
                            <th className="p-3 text-right">{t('积分', 'Credits')}</th>
                            <th className="p-3 text-center whitespace-nowrap" title={t('是否允许扣用户组积分', 'Allow deducting group credits')}>
                                {t('扣组积分', 'Group bill')}
                            </th>
                            <th className="p-3">{t('创建时间', 'Created')}</th>
                            <th className="p-3">{t('操作', 'Actions')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {groups.map((group) => (
                            <tr key={group.id} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                                <td className="p-3 font-mono text-xs text-gray-300">{group.id}</td>
                                <td className="p-3">
                                    <input
                                        className="w-full bg-black/30 border border-gray-700 rounded px-2 py-1 text-sm"
                                        value={group.name || ''}
                                        onChange={(e) => patchGroupLocal(group.id, { name: e.target.value })}
                                        onBlur={() => saveGroupField(group.id, { name: group.name })}
                                    />
                                </td>
                                <td className="p-3">
                                    <input
                                        className="w-full bg-black/30 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300"
                                        value={group.description || ''}
                                        onChange={(e) => patchGroupLocal(group.id, { description: e.target.value })}
                                        onBlur={() => saveGroupField(group.id, { description: group.description || '' })}
                                    />
                                </td>
                                <td className="p-3 text-sm">
                                    <div>{group.owner_username || '-'}</div>
                                    <div className="text-xs text-gray-500">{group.owner_email || (group.owner_id ? `#${group.owner_id}` : '')}</div>
                                </td>
                                <td className="p-3 text-right font-mono">{group.member_count ?? 0}</td>
                                <td className="p-3 text-right font-mono text-green-400">
                                    {group.credits ?? 0}
                                    <button
                                        onClick={() => { setCreditEditGroup(group); setCreditAmount(group.credits || 0); }}
                                        className="ml-2 text-gray-500 hover:text-white"
                                    >
                                        <Edit2 size={12} className="inline" />
                                    </button>
                                </td>
                                <td className="p-3 text-center">
                                    <input
                                        type="checkbox"
                                        className="h-4 w-4 accent-primary"
                                        title={t('允许扣组积分（默认关）', 'Allow group credit billing (off by default)')}
                                        checked={Boolean(group.allow_group_credit_billing)}
                                        onChange={(e) => {
                                            const next = e.target.checked;
                                            patchGroupLocal(group.id, { allow_group_credit_billing: next });
                                            saveGroupField(group.id, { allow_group_credit_billing: next });
                                        }}
                                    />
                                </td>
                                <td className="p-3 text-xs text-gray-400">{group.created_at || '-'}</td>
                                <td className="p-3">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <button
                                            onClick={() => openMembers(group)}
                                            className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20"
                                        >
                                            {t('成员', 'Members')}
                                        </button>
                                        <button
                                            onClick={() => { setAddingToGroup(group); setNewMemberInput(''); }}
                                            className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20"
                                        >
                                            {t('+ 成员', '+ Member')}
                                        </button>
                                        <button
                                            onClick={() => handleDeleteGroup(group)}
                                            className="text-xs px-2 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-300"
                                        >
                                            <Trash2 size={12} className="inline" />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                        {!loading && groups.length === 0 && (
                            <tr>
                                <td colSpan={9} className="p-8 text-center text-gray-400">
                                    {t('暂无用户组', 'No groups')}
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {creditEditGroup && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
                    <div className="bg-[#1a1b26] border border-white/10 rounded-xl p-6 w-full max-w-sm shadow-2xl">
                        <h3 className="text-lg font-bold mb-2">{t('调整组积分', 'Adjust Group Credits')}</h3>
                        <p className="text-sm text-gray-400 mb-4">{creditEditGroup.name}</p>
                        <input
                            type="number"
                            className="w-full bg-black/40 border border-white/10 rounded-md px-3 py-2 text-sm mb-4"
                            value={creditAmount}
                            onChange={(e) => setCreditAmount(e.target.value)}
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => setCreditEditGroup(null)}
                                className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-sm"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button
                                onClick={handleSaveCredits}
                                className="px-3 py-1.5 rounded bg-primary text-black font-medium text-sm"
                            >
                                {t('保存', 'Save')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {addingToGroup && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
                    <div className="bg-[#1a1b26] border border-white/10 rounded-xl p-6 w-full max-w-md shadow-2xl">
                        <h3 className="text-lg font-bold mb-2">{t('添加成员', 'Add Members')}</h3>
                        <p className="text-sm text-gray-400 mb-4">{addingToGroup.name}</p>
                        <textarea
                            rows={5}
                            className="w-full bg-black/40 border border-white/10 rounded-md px-3 py-2 text-sm resize-y mb-2"
                            placeholder={t('用户名或邮箱，支持逗号/空格/换行批量添加', 'Usernames or emails, comma/space/newline separated')}
                            value={newMemberInput}
                            onChange={(e) => setNewMemberInput(e.target.value)}
                            autoFocus
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => { setAddingToGroup(null); setNewMemberInput(''); }}
                                className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-sm"
                            >
                                {t('取消', 'Cancel')}
                            </button>
                            <button
                                onClick={handleAddMembers}
                                className="px-3 py-1.5 rounded bg-primary text-black font-medium text-sm"
                            >
                                {t('确认添加', 'Add')}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {viewingGroup && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
                    <div className="bg-[#1a1b26] border border-white/10 rounded-xl p-6 w-full max-w-3xl shadow-2xl max-h-[90vh] overflow-y-auto">
                        <div className="flex items-start justify-between gap-3 mb-4">
                            <div>
                                <h3 className="text-lg font-bold flex items-center gap-2">
                                    <Users size={18} className="text-primary" />
                                    {t('成员列表', 'Members')}
                                </h3>
                                <p className="text-sm text-gray-400 mt-1">
                                    {viewingGroup.name}
                                    <span className="ml-2 text-white/50">({members.length || viewingGroup.member_count || 0})</span>
                                    <span className="ml-3 text-green-400/90 font-mono text-xs">
                                        {t('组积分', 'Group credits')}: {viewingGroup.credits ?? 0}
                                    </span>
                                </p>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => { setAddingToGroup(viewingGroup); setNewMemberInput(''); }}
                                    className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-sm"
                                >
                                    {t('+ 添加', '+ Add')}
                                </button>
                                <button
                                    onClick={() => { setViewingGroup(null); setMembers([]); }}
                                    className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-sm"
                                >
                                    {t('关闭', 'Close')}
                                </button>
                            </div>
                        </div>
                        <div className="rounded-lg border border-white/10 overflow-hidden bg-black/40 max-h-[36vh] overflow-y-auto mb-4">
                            <table className="w-full text-left border-collapse text-sm">
                                <thead className="sticky top-0 bg-[#1a1b26]">
                                    <tr className="border-b border-white/10 text-gray-400">
                                        <th className="p-3">{t('用户', 'User')}</th>
                                        <th className="p-3">{t('邮箱', 'Email')}</th>
                                        <th className="p-3 text-right">{t('个人积分', 'Personal')}</th>
                                        <th className="p-3">{t('角色', 'Role')}</th>
                                        <th className="p-3 text-right">{t('操作', 'Actions')}</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {loadingMembers && (
                                        <tr>
                                            <td colSpan={5} className="p-6 text-center text-gray-400">
                                                {t('加载中…', 'Loading…')}
                                            </td>
                                        </tr>
                                    )}
                                    {!loadingMembers && members.map((m) => (
                                        <tr key={m.user_id} className="border-b border-white/5">
                                            <td className="p-3">
                                                {m.username || '-'}
                                                {m.full_name ? <span className="ml-2 text-xs text-white/40">{m.full_name}</span> : null}
                                            </td>
                                            <td className="p-3 text-gray-400">{m.email || '-'}</td>
                                            <td className="p-3 text-right font-mono text-gray-300">{m.personal_credits ?? 0}</td>
                                            <td className="p-3">
                                                <button
                                                    onClick={() => handleToggleMemberRole(m)}
                                                    className="text-xs px-2 py-1 rounded bg-white/10 hover:bg-white/20"
                                                    title={t('点击切换管理员/成员', 'Click to toggle admin/member')}
                                                >
                                                    {m.permission_level >= 2 ? t('管理员', 'Admin') : t('成员', 'Member')}
                                                </button>
                                            </td>
                                            <td className="p-3 text-right">
                                                <button
                                                    onClick={() => handleRemoveMember(m)}
                                                    className="text-xs px-2 py-1 rounded bg-red-500/20 hover:bg-red-500/30 text-red-300"
                                                >
                                                    {t('移除', 'Remove')}
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                    {!loadingMembers && members.length === 0 && (
                                        <tr>
                                            <td colSpan={5} className="p-6 text-center text-gray-400">
                                                {t('暂无成员', 'No members')}
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                        {!loadingMembers && members.length > 0 && (
                            <GroupCreditAllocatePanel
                                groupId={viewingGroup.id}
                                groupCredits={viewingGroup.credits ?? 0}
                                members={members}
                                onAllocated={async (res) => {
                                    patchGroupLocal(viewingGroup.id, { credits: res?.group_credits ?? 0 });
                                    await refreshMembers(viewingGroup.id);
                                    alert(t(
                                        `已分配 ${res?.total_allocated ?? 0} 积分，组剩余 ${res?.group_credits ?? 0}`,
                                        `Allocated ${res?.total_allocated ?? 0}; group remaining ${res?.group_credits ?? 0}`
                                    ));
                                }}
                            />
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
