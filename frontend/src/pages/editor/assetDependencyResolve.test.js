import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
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
