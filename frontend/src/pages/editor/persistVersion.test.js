import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { formatPersistedClock, formatPersistedGap, latestPersistIso } from './persistVersion.js';

describe('persistVersion', () => {
    it('shows Beijing hour and minute and drops seconds', () => {
        assert.equal(formatPersistedClock('2026-11-23T15:14:59.123456+08:00'), '15时14分');
        assert.equal(formatPersistedClock('2026-11-23T07:05:01.000Z'), '15时05分');
    });

    it('returns empty for a missing or unreadable clock', () => {
        assert.equal(formatPersistedClock(''), '');
        assert.equal(formatPersistedClock('not-a-time'), '');
    });

    it('shows the gap from now and stops at minutes', () => {
        const now = Date.parse('2026-11-24T00:19:40+08:00');
        assert.deepEqual(
            formatPersistedGap('2026-11-24T00:19:05+08:00', now),
            { zh: '刚刚', en: 'just now' },
        );
        assert.deepEqual(
            formatPersistedGap('2026-11-24T00:07:59+08:00', now),
            { zh: '11分钟前', en: '11m ago' },
        );
        assert.deepEqual(
            formatPersistedGap('2026-11-23T21:19:40+08:00', now),
            { zh: '3小时前', en: '3h ago' },
        );
        assert.deepEqual(
            formatPersistedGap('2026-11-23T15:14:59.123456+08:00', now),
            { zh: '9小时4分前', en: '9h 4m ago' },
        );
        assert.deepEqual(
            formatPersistedGap('2026-11-21T21:19:40+08:00', now),
            { zh: '2天3小时前', en: '2d 3h ago' },
        );
        assert.equal(formatPersistedGap('', now), null);
        assert.equal(formatPersistedGap('not-a-time', now), null);
    });

    it('picks the later successful persist', () => {
        assert.equal(
            latestPersistIso(
                '2026-11-23T15:14:00+08:00',
                '2026-11-23T15:20:10+08:00',
            ),
            '2026-11-23T15:20:10+08:00',
        );
    });
});
