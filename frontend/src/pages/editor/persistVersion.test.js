import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { formatPersistedClock, latestPersistIso } from './persistVersion.js';

describe('persistVersion', () => {
    it('shows Beijing hour and minute and drops seconds', () => {
        assert.equal(formatPersistedClock('2026-11-23T15:14:59.123456+08:00'), '15时14分');
        assert.equal(formatPersistedClock('2026-11-23T07:05:01.000Z'), '15时05分');
    });

    it('returns empty for a missing or unreadable clock', () => {
        assert.equal(formatPersistedClock(''), '');
        assert.equal(formatPersistedClock('not-a-time'), '');
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
