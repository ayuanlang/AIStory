import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { extractOrderedTypedEntityRefs, unmatchedTypedEntityRefs } from './shotRefSlots.js';

const PROMPT = [
    'CHAR:[@林薇薇] 站在全息屏办公台远离镜头的那一侧。',
    'CHAR:[@顾沉舟_重生当日] 坐在办公台后的座上。',
    'PROP:[热饮杯] 由 CHAR:[@林薇薇] 双手托着。',
    '背景参考图为 ENV:[180度总裁室]。',
].join('');

describe('unmatched environment still keeps a reference slot', () => {
    it('reads typed names in prompt order and skips a repeated character', () => {
        const refs = extractOrderedTypedEntityRefs(PROMPT);
        assert.deepEqual(refs.map((ref) => ref.name), [
            '林薇薇',
            '顾沉舟_重生当日',
            '热饮杯',
            '180度总裁室',
        ]);
        assert.equal(refs[3].type, 'environment');
    });

    it('keeps a slot name when the environment asset was never generated', () => {
        const pool = [
            { id: 1, name: '林薇薇', type: 'character', image_url: 'lin.png' },
            { id: 2, name: '顾沉舟_重生当日', type: 'character', image_url: 'gu.png' },
            { id: 3, name: '热饮杯', type: 'prop', image_url: 'cup.png' },
            { id: 4, name: '总裁室', type: 'environment', image_url: 'quad.png' },
        ];
        const missing = unmatchedTypedEntityRefs({
            promptText: PROMPT,
            includeAssociatedEntities: false,
            entityPool: pool,
        });
        assert.deepEqual(missing.map((ref) => ref.name), ['180度总裁室']);
        assert.equal(missing[0].type, 'environment');
    });

    it('does not add a second slot when the asset row exists but has no image', () => {
        const pool = [
            { id: 9, name: '180度总裁室', type: 'environment', image_url: '' },
        ];
        const missing = unmatchedTypedEntityRefs({
            promptText: '背景参考图为 ENV:[180度总裁室]。',
            entityPool: pool,
        });
        assert.deepEqual(missing, []);
    });
});
