import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
    isThisRunPipelineNode,
    shouldHoldStoryboardKickoffForQueuedPlaceholder,
    shouldRejectLeftoverStagingKickoff,
} from './analysisRestartGuards.js';

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

    it('rejects staging that finishes after the new clock but is not in this run', () => {
        const runStartedAt = Date.parse('2026-09-18T16:57:49.000Z');
        const latePreviousRun = {
            node_name: 'scene_subskill_scene',
            status: 'success',
            scene_id: 'EP01_SC02',
            updated_at: '2026-09-18T17:10:00.000Z',
        };
        assert.equal(isThisRunPipelineNode(latePreviousRun, runStartedAt), true);
        assert.equal(shouldRejectLeftoverStagingKickoff({
            fullRestartGate: true,
            node: latePreviousRun,
            runStartedAt,
        }), true);
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

    it('holds shot kickoff while queued storyboard is newer than leftover staging', () => {
        const staging = {
            status: 'success',
            ended_at: '2026-09-25T00:30:00',
            updated_at: '2026-09-25T00:30:00',
        };
        const queued = {
            status: 'queued',
            updated_at: '2026-09-25T01:25:11',
            runtime_meta: { business_event: 'queued', rerun_cleared: true },
        };
        assert.equal(shouldHoldStoryboardKickoffForQueuedPlaceholder(staging, queued), true);
    });

    it('releases shot kickoff after this-run staging finishes later than the queue', () => {
        const staging = {
            status: 'success',
            started_at: '2026-09-25T01:25:11',
            ended_at: '2026-09-25T01:40:00',
            updated_at: '2026-09-25T01:40:00',
        };
        const queued = {
            status: 'queued',
            started_at: '2026-09-25T01:25:11',
            updated_at: '2026-09-25T01:25:11',
            runtime_meta: { business_event: 'queued', rerun_cleared: true },
        };
        assert.equal(shouldHoldStoryboardKickoffForQueuedPlaceholder(staging, queued), false);
    });

    it('does not hold kickoff when storyboard is already a finished node', () => {
        assert.equal(shouldHoldStoryboardKickoffForQueuedPlaceholder(
            { status: 'success', ended_at: '2026-09-25T00:30:00' },
            { status: 'success', updated_at: '2026-09-25T00:46:58' },
        ), false);
    });

    it('parses naive Beijing timestamps as this-run nodes', () => {
        const runStartedAt = Date.parse('2026-09-18T14:00:00.000Z');
        assert.equal(isThisRunPipelineNode({
            updated_at: '2026-09-18 22:10:00.123456',
        }, runStartedAt), true);
    });
});
