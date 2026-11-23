/** Hour and minute of a successful persist. This clock is the version. */

export function formatPersistedClock(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    const parsed = new Date(text);
    if (Number.isNaN(parsed.getTime())) return '';
    const parts = new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Asia/Shanghai',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
    }).formatToParts(parsed);
    const hour = parts.find((part) => part.type === 'hour')?.value || '';
    const minute = parts.find((part) => part.type === 'minute')?.value || '';
    if (!hour || !minute) return '';
    return `${hour}时${minute}分`;
}

export function latestPersistIso(...values) {
    let best = '';
    let bestMs = Number.NEGATIVE_INFINITY;
    values.flat().forEach((value) => {
        const text = String(value || '').trim();
        if (!text) return;
        const ms = Date.parse(text);
        if (Number.isNaN(ms) || ms < bestMs) return;
        best = text;
        bestMs = ms;
    });
    return best;
}
