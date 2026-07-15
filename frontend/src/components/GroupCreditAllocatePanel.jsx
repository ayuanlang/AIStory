import React, { useEffect, useMemo, useState } from 'react';
import { allocateGroupCredits } from '../services/api';
import { getUiLang, tUI } from '../lib/uiLang';
import { confirmUiMessage } from '../lib/uiMessage';

function buildEqualMap(userIds, totalAmount) {
    const ids = (userIds || []).map((id) => Number(id)).filter((id) => Number.isFinite(id));
    const total = Math.max(0, Math.floor(Number(totalAmount) || 0));
    const map = {};
    if (ids.length === 0 || total <= 0) {
        ids.forEach((id) => { map[id] = 0; });
        return map;
    }
    const base = Math.floor(total / ids.length);
    let rem = total % ids.length;
    ids.forEach((id, i) => {
        map[id] = base + (i < rem ? 1 : 0);
    });
    return map;
}

/**
 * Allocate shared group credits to members' personal balances.
 * Modes: equal-all / equal-amount (then editable) / custom manual.
 */
export default function GroupCreditAllocatePanel({
    groupId,
    groupCredits = 0,
    members = [],
    onAllocated,
    compact = false,
}) {
    const uiLang = getUiLang();
    const t = (zh, en) => tUI(uiLang, zh, en);

    const [selectedIds, setSelectedIds] = useState([]);
    const [amounts, setAmounts] = useState({});
    const [equalTotal, setEqualTotal] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        const ids = (members || []).map((m) => m.user_id);
        setSelectedIds(ids);
        setAmounts({});
        setEqualTotal(String(Math.max(0, Number(groupCredits) || 0)));
        setError('');
    }, [groupId, members, groupCredits]);

    const pool = Math.max(0, Number(groupCredits) || 0);

    const totalPlanned = useMemo(() => (
        selectedIds.reduce((sum, id) => sum + Math.max(0, Math.floor(Number(amounts[id]) || 0)), 0)
    ), [selectedIds, amounts]);

    const remaining = pool - totalPlanned;

    const toggleSelected = (userId) => {
        setSelectedIds((prev) => (
            prev.includes(userId) ? prev.filter((id) => id !== userId) : [...prev, userId]
        ));
    };

    const selectAll = () => setSelectedIds((members || []).map((m) => m.user_id));
    const selectNone = () => setSelectedIds([]);

    const applyEqual = (total) => {
        const ids = selectedIds.length > 0 ? selectedIds : (members || []).map((m) => m.user_id);
        if (ids.length === 0) {
            setError(t('请先选择成员', 'Select members first'));
            return;
        }
        const capped = Math.min(Math.max(0, Math.floor(Number(total) || 0)), pool);
        const next = buildEqualMap(ids, capped);
        const cleared = {};
        (members || []).forEach((m) => { cleared[m.user_id] = 0; });
        setAmounts({ ...cleared, ...next });
        setSelectedIds(ids);
        setError('');
    };

    const handleAmountChange = (userId, value) => {
        const n = value === '' ? '' : Math.max(0, Math.floor(Number(value) || 0));
        setAmounts((prev) => ({ ...prev, [userId]: n }));
        if (!selectedIds.includes(userId) && Number(n) > 0) {
            setSelectedIds((prev) => [...prev, userId]);
        }
    };

    const handleSubmit = async () => {
        const allocations = selectedIds
            .map((user_id) => ({
                user_id,
                amount: Math.max(0, Math.floor(Number(amounts[user_id]) || 0)),
            }))
            .filter((row) => row.amount > 0);

        if (allocations.length === 0) {
            setError(t('请填写要分配的积分', 'Enter allocation amounts'));
            return;
        }
        const sum = allocations.reduce((s, r) => s + r.amount, 0);
        if (sum > pool) {
            setError(t(`合计 ${sum} 超过组积分 ${pool}`, `Total ${sum} exceeds group credits ${pool}`));
            return;
        }

        const ok = await confirmUiMessage(
            t(
                `确认将 ${sum} 组积分分配给 ${allocations.length} 名成员？分配后计入各成员个人积分。`,
                `Allocate ${sum} group credits to ${allocations.length} member(s)? Credits will move to personal balances.`
            )
        );
        if (!ok) return;

        setSubmitting(true);
        setError('');
        try {
            const res = await allocateGroupCredits(groupId, {
                mode: 'custom',
                allocations,
            });
            if (typeof onAllocated === 'function') {
                onAllocated(res);
            }
            setAmounts({});
        } catch (e) {
            console.error(e);
            setError(e?.response?.data?.detail || e?.message || t('分配失败', 'Allocation failed'));
        } finally {
            setSubmitting(false);
        }
    };

    if (!members?.length) {
        return (
            <div className="text-xs text-gray-500 py-2">
                {t('暂无成员可分配', 'No members to allocate')}
            </div>
        );
    }

    return (
        <div className={`rounded-lg border border-white/10 bg-black/30 ${compact ? 'p-3' : 'p-4'} space-y-3`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                    <div className="text-sm font-medium text-white">{t('分配组积分', 'Allocate Group Credits')}</div>
                    <div className="text-xs text-gray-400 mt-0.5">
                        {t('组可用', 'Available')}: <span className="text-green-400 font-mono">{pool}</span>
                        <span className="mx-2 text-white/20">|</span>
                        {t('本次合计', 'This batch')}: <span className={`font-mono ${remaining < 0 ? 'text-red-400' : 'text-primary'}`}>{totalPlanned}</span>
                        <span className="mx-2 text-white/20">|</span>
                        {t('分配后剩余', 'After')}: <span className={`font-mono ${remaining < 0 ? 'text-red-400' : 'text-gray-300'}`}>{remaining}</span>
                    </div>
                </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
                <button
                    type="button"
                    onClick={() => applyEqual(pool)}
                    className="text-xs px-2.5 py-1.5 rounded bg-white/10 hover:bg-white/20"
                    disabled={pool <= 0}
                >
                    {t('平均分全部', 'Equal (all)')}
                </button>
                <div className="flex items-center gap-1">
                    <input
                        type="number"
                        min={0}
                        max={pool}
                        className="w-24 bg-black/40 border border-white/10 rounded px-2 py-1 text-xs font-mono"
                        value={equalTotal}
                        onChange={(e) => setEqualTotal(e.target.value)}
                        placeholder={t('额度', 'Amount')}
                    />
                    <button
                        type="button"
                        onClick={() => applyEqual(equalTotal)}
                        className="text-xs px-2.5 py-1.5 rounded bg-white/10 hover:bg-white/20"
                    >
                        {t('平均分此额度', 'Equal (amount)')}
                    </button>
                </div>
                <button
                    type="button"
                    onClick={() => {
                        const cleared = {};
                        (members || []).forEach((m) => { cleared[m.user_id] = 0; });
                        setAmounts(cleared);
                        setError('');
                    }}
                    className="text-xs px-2.5 py-1.5 rounded bg-white/5 hover:bg-white/10 text-gray-300"
                >
                    {t('清空', 'Clear')}
                </button>
                <button type="button" onClick={selectAll} className="text-xs px-2 py-1 text-gray-400 hover:text-white">
                    {t('全选', 'All')}
                </button>
                <button type="button" onClick={selectNone} className="text-xs px-2 py-1 text-gray-400 hover:text-white">
                    {t('全不选', 'None')}
                </button>
            </div>

            <p className="text-[11px] text-gray-500">
                {t('可先用固定模式预填，再手动微调每人金额后确认分配。', 'Use a preset to prefill, then manually adjust each amount before confirming.')}
            </p>

            <div className={`rounded border border-white/5 overflow-hidden ${compact ? 'max-h-48' : 'max-h-56'} overflow-y-auto`}>
                <table className="w-full text-left text-xs">
                    <thead className="sticky top-0 bg-[#15161f] text-gray-400">
                        <tr className="border-b border-white/10">
                            <th className="p-2 w-8"></th>
                            <th className="p-2">{t('成员', 'Member')}</th>
                            <th className="p-2 text-right">{t('个人积分', 'Personal')}</th>
                            <th className="p-2 text-right w-28">{t('分配', 'Allocate')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(members || []).map((m) => {
                            const checked = selectedIds.includes(m.user_id);
                            return (
                                <tr key={m.user_id} className="border-b border-white/5">
                                    <td className="p-2">
                                        <input
                                            type="checkbox"
                                            checked={checked}
                                            onChange={() => toggleSelected(m.user_id)}
                                        />
                                    </td>
                                    <td className="p-2">
                                        <div className="text-white">{m.username || m.email || m.user_id}</div>
                                        {m.email && m.username ? (
                                            <div className="text-[10px] text-gray-500">{m.email}</div>
                                        ) : null}
                                    </td>
                                    <td className="p-2 text-right font-mono text-gray-400">
                                        {m.personal_credits ?? 0}
                                    </td>
                                    <td className="p-2 text-right">
                                        <input
                                            type="number"
                                            min={0}
                                            className="w-24 bg-black/40 border border-white/10 rounded px-2 py-1 text-right font-mono"
                                            value={amounts[m.user_id] ?? ''}
                                            onChange={(e) => handleAmountChange(m.user_id, e.target.value)}
                                            disabled={!checked}
                                            placeholder="0"
                                        />
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {error && (
                <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded px-2 py-1.5">
                    {error}
                </div>
            )}

            <div className="flex justify-end">
                <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={submitting || totalPlanned <= 0 || remaining < 0 || pool <= 0}
                    className="px-3 py-1.5 rounded bg-primary text-black font-medium text-sm disabled:opacity-40"
                >
                    {submitting ? t('分配中…', 'Allocating…') : t('确认分配', 'Confirm Allocate')}
                </button>
            </div>
        </div>
    );
}
