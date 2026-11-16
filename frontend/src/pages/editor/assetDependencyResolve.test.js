import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
    buildCurrentBoundPickerRows,
    episodeDisplayNumber,
    episodeSortNumber,
    pickNearestEpisodeSameNameReuseSource,
    resolveDependencyEntity,
} from './assetDependencyResolve.js';

const episodeNumberOf = (map) => (episodeId) => {
    const key = String(episodeId || '').trim();
    if (!Object.prototype.hasOwnProperty.call(map, key)) return 0;
    return map[key];
};

describe('resolveDependencyEntity', () => {
    const entities = [
        { id: 1, name: '林月', type: 'character', episode_id: 'ep1', image_url: 'ep1.png' },
        { id: 2, name: '林月', type: 'character', episode_id: 'ep2', image_url: 'ep2.png' },
        { id: 4, name: '林月', type: 'character', episode_id: 'ep4', image_url: 'ep4.png' },
    ];
    const numbers = episodeNumberOf({ ep1: 1, ep2: 2, ep3: 3, ep4: 4 });

    it('prefers the host episode over an earlier episode', () => {
        const hit = resolveDependencyEntity('CHAR:[@林月]', entities, 'ep2', numbers);
        assert.equal(hit.id, 2);
    });

    it('uses the nearest earlier episode when the host episode has no row', () => {
        const hit = resolveDependencyEntity('林月', entities, 'ep3', numbers);
        assert.equal(hit.id, 2);
    });

    it('does not use a later episode', () => {
        const hit = resolveDependencyEntity('林月', [entities[2]], 'ep3', numbers);
        assert.equal(hit, null);
    });

    it('keeps an explicit entity id even when that row is a later episode', () => {
        const hit = resolveDependencyEntity('entity id: 4', entities, 'ep3', numbers);
        assert.equal(hit.id, 4);
    });
});

describe('pickNearestEpisodeSameNameReuseSource', () => {
    const pool = [
        { id: 11, name: '林月', type: 'character', episode_id: 'ep1', image_url: 'a.png', visual_dependencies: [] },
        { id: 12, name: '林月', type: 'character', episode_id: 'ep2', image_url: 'b.png', visual_dependencies: [] },
        { id: 16, name: '林月', type: 'character', episode_id: 'ep6', image_url: 'c.png', visual_dependencies: [] },
        { id: 21, name: '玉佩', type: 'prop', episode_id: 'ep4', image_url: 'prop.png', visual_dependencies: [] },
    ];
    const numbers = episodeNumberOf({ ep1: 1, ep2: 2, ep4: 4, ep5: 5, ep6: 6 });
    const reusable = () => true;

    it('copies the host name from the nearest previous episode, not the dependency name', () => {
        const host = {
            id: 50,
            name: '林月_夏装',
            type: 'character',
            episode_id: 'ep5',
            visual_dependencies: ['CHAR:[@林月]'],
        };
        const withCostume = [
            ...pool,
            { id: 14, name: '林月_夏装', type: 'character', episode_id: 'ep4', image_url: 'summer.png' },
            { id: 13, name: '林月_夏装', type: 'character', episode_id: 'ep2', image_url: 'old-summer.png' },
        ];
        const hit = pickNearestEpisodeSameNameReuseSource(host, withCostume, numbers, reusable);
        assert.equal(hit.id, 14);
    });

    it('ignores a closer future episode', () => {
        const host = {
            id: 50,
            name: '林月',
            type: 'character',
            episode_id: 'ep5',
            visual_dependencies: ['CHAR:[@林月]'],
        };
        const hit = pickNearestEpisodeSameNameReuseSource(host, pool, numbers, reusable);
        assert.equal(hit.id, 12);
    });

    it('does not copy a nearer subject of another type', () => {
        const host = {
            id: 60,
            name: '林月',
            type: 'character',
            episode_id: 'ep5',
            visual_dependencies: ['PROP:[玉佩]'],
        };
        const mixed = [
            { id: 12, name: '林月', type: 'character', episode_id: 'ep2', image_url: 'b.png' },
            { id: 21, name: '林月', type: 'prop', episode_id: 'ep4', image_url: 'prop.png' },
        ];
        const hit = pickNearestEpisodeSameNameReuseSource(host, mixed, numbers, reusable);
        assert.equal(hit.id, 12);
    });

    it('returns null when the subject has no asset dependency', () => {
        const host = {
            id: 70,
            name: '林月',
            type: 'character',
            episode_id: 'ep5',
            visual_dependencies: [],
        };
        const hit = pickNearestEpisodeSameNameReuseSource(host, pool, numbers, reusable);
        assert.equal(hit, null);
    });
});

describe('episodeSortNumber', () => {
    it('prefers the script episode number over the list index', () => {
        const episode = {
            title: 'Episode 9',
            episode_info: { episode_script_episode_number: 3, episode_number: 8 },
        };
        assert.equal(episodeSortNumber(episode, 0), 3);
    });
});

describe('episodeDisplayNumber', () => {
    const episodes = [
        { id: 'ep3', title: 'Episode 3', episode_number: 3 },
        { id: 'ep2', title: 'Episode 2' },
        { id: 'ep1', title: '开篇', episode_info: { episode_script_episode_number: 9, story_dna_episode_number: 12 } },
    ];

    it('uses the editor episode number, not the script or story-dna number', () => {
        assert.equal(episodeDisplayNumber(episodes[0], episodes), 3);
        assert.equal(episodeDisplayNumber(episodes[1], episodes), 2);
        assert.equal(episodeDisplayNumber(episodes[2], episodes), 1);
    });

    it('does not number a deleted episode', () => {
        assert.equal(episodeDisplayNumber({ id: 'gone', title: 'Episode 4', is_deleted: true }, episodes), null);
    });
});

describe('buildCurrentBoundPickerRows', () => {
    const episodes = [
        { id: 'ep2', title: 'Episode 2', episode_number: 2 },
        { id: 'ep1', title: 'Episode 1', episode_number: 1 },
    ];
    const entities = [
        { id: 1, name: '林月', type: 'character', episode_id: 'ep1', image_url: 'current-1.png' },
        { id: 2, name: '林月', type: 'character', episode_id: 'ep2', image_url: 'current-2.png', is_deleted: true },
        { id: 3, name: '玉佩', type: 'prop', episode_id: 'ep2', image_url: 'https://file.aitohumanize.com/old.png' },
        { id: 4, name: '旧椅', type: 'prop', episode_id: 'gone', image_url: 'chair.png' },
        { id: 5, name: '书案', type: 'prop', episode_id: 'ep1', image_url: 'desk.png' },
        { id: 6, name: '茶盏', type: 'prop', episode_id: 'ep2', image_url: 'cup.png' },
    ];
    const assets = [
        { id: 101, url: 'old-1.png', is_deleted: false, meta_info: { entity_id: 1, episode_id: 'ep9' } },
        { id: 102, url: 'current-1.png', is_deleted: false, meta_info: { entity_id: 1, episode_id: 'ep9' } },
        { id: 103, url: 'current-2.png', is_deleted: false, meta_info: { entity_id: 2 } },
        { id: 104, url: 'desk.png', is_deleted: true, meta_info: { entity_id: 5 } },
    ];
    const collectTokens = (url) => {
        const text = String(url || '').trim().toLowerCase();
        return text ? new Set([text]) : new Set();
    };

    it('keeps only the current image of a live subject on a live episode', () => {
        const rows = buildCurrentBoundPickerRows({
            entities,
            assets,
            episodes,
            excludeEntityId: '',
            isEphemeral: (url) => String(url).includes('aitohumanize.com'),
            collectTokens,
        });
        assert.deepEqual(rows.map((row) => row.entity_id), ['1', '6']);
        assert.equal(rows[0].url, 'current-1.png');
        assert.equal(rows[0].episode_id, 'ep1');
        assert.equal(rows[0].bound_episode_number, 1);
        assert.equal(rows[0].meta_info.episode_id, 'ep1');
    });
});
