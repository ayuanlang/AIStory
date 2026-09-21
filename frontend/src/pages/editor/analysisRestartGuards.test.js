import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { isThisRunPipelineNode, shouldRejectLeftoverStagingKickoff } from './analysisRestartGuards.js';

describe('analysisRestartGuards', () => {
    it('rejects leftover staging nodes after a full restart clock starts', () => {
        const runStartedAt = Date.parse('2026-09-18T16:57:49.000Z');
        const leftover = {
            node_name: 'scene_subskill_scene',
            status: 'success',
            scene_id: 'EP01_SC01',
            updated_at: '2026-09-18T10:00:00.000Z',
        };
        assert.equal(isThisRunPipelineNode(leftover, runStartedAt), false);
        assert.equal(shouldRejectLeftoverStagingKickoff({
            fullRestartGate: true,
            node: leftover,
            runStartedAt,
        }), true);
    });

    it('keeps this-run staging nodes after the restart clock', () => {
        const runStartedAt = Date.parse('2026-09-18T16:57:49.000Z');
        const thisRun = {
            node_name: 'scene_subskill_scene',
            status: 'success',
            scene_id: 'EP01_SC01',
            updated_at: '2026-09-18T17:10:00.000Z',
        };
        assert.equal(isThisRunPipelineNode(thisRun, runStartedAt), true);
        assert.equal(shouldRejectLeftoverStagingKickoff({
            fullRestartGate: true,
            node: thisRun,
            runStartedAt,
        }), false);
    });

    it('allows this-run allowlist scenes even if the staging timestamp looks old', () => {
        const leftover = {
            updated_at: '2026-09-18T10:00:00.000Z',
        };
        assert.equal(shouldRejectLeftoverStagingKickoff({
            fullRestartGate: true,
            node: leftover,
            runStartedAt: Date.parse('2026-09-18T16:57:49.000Z'),
            inThisRunAllowlist: true,
        }), false);
    });

    it('does not reject after the restart ENV gate has opened', () => {
        const leftover = {
            updated_at: '2026-09-18T10:00:00.000Z',
        };
        assert.equal(shouldRejectLeftoverStagingKickoff({
            fullRestartGate: false,
            node: leftover,
            runStartedAt: Date.now(),
        }), false);
    });

    it('does not reject this-run staging when the analysis clock is missing', () => {
        assert.equal(shouldRejectLeftoverStagingKickoff({
            fullRestartGate: true,
            node: { updated_at: '2026-09-18T17:10:00.000Z' },
            runStartedAt: 0,
        }), false);
    });

    it('parses naive Beijing timestamps as this-run nodes', () => {
        const runStartedAt = Date.parse('2026-09-18T14:00:00.000Z');
        assert.equal(isThisRunPipelineNode({
            updated_at: '2026-09-18 22:10:00.123456',
        }, runStartedAt), true);
    });
});
