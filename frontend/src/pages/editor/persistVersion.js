/** Hour and minute of a successful persist. This clock is the version. */

const MINUTE_MS = 60 * 1000;

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

/** Gap from a persist stamp to now. Minutes are the smallest unit. */
export function formatPersistedGap(value, nowMs = Date.now()) {
    const text = String(value || '').trim();
    if (!text) return null;
    const parsed = Date.parse(text);
    const now = Number(nowMs);
    if (Number.isNaN(parsed) || !Number.isFinite(now)) return null;
    const minutes = Math.floor(Math.max(0, now - parsed) / MINUTE_MS);
    if (minutes < 1) {
        return { zh: '刚刚', en: 'just now' };
    }
    if (minutes < 60) {
        return { zh: `${minutes}分钟前`, en: `${minutes}m ago` };
    }
    const hours = Math.floor(minutes / 60);
    const remainMinutes = minutes % 60;
    if (hours < 24) {
        if (remainMinutes === 0) {
            return { zh: `${hours}小时前`, en: `${hours}h ago` };
        }
        return { zh: `${hours}小时${remainMinutes}分前`, en: `${hours}h ${remainMinutes}m ago` };
    }
    const days = Math.floor(hours / 24);
    const remainHours = hours % 24;
    if (remainHours === 0) {
        return { zh: `${days}天前`, en: `${days}d ago` };
    }
    return { zh: `${days}天${remainHours}小时前`, en: `${days}d ${remainHours}h ago` };
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
