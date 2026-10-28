import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
    beatOptionLabel,
    buildBeatViewerScenes,
    findNodeBeat,
    matchWorkspaceScene,
    mergePipelineSceneBlocks,
    mergeSubskillResultMaps,
    normalizeStoryboardShots,
    parseMergedBeatIds,
    parseNodeBeats,
    shotsCoveringBeat,
    splitStagingBeat,
    WHOLE_NODE_BEAT_ID,
} from './beatViewer.js';

const drama = `
[SCENE_START:EP01_SC02]
【场景名称】总裁办公室｜日·内
[BEAT_START:1]
- Beat 1｜救猫咪拍=开场画面：
陆沉推门进来。
[BEAT_END:1]
[BEAT_START:02]
~ Beat 2：
他看见桌上的合同。
[BEAT_END:02]
[SCENE_END:EP01_SC02]
`;

const staging = `
[BEAT_STREAM_START]
[BEAT_START:1]
- Beat 1：节拍=开场画面
────【建置】────
镜头在门内。
────【入戏】────
陆沉推门进来。
────【场记分析】────
开拍在场角色数=1
────【场记分析结束】────
[BEAT_END:1]
[BEAT_STREAM_END]
`;

describe('parseNodeBeats', () => {
    it('reads beat ids and keeps the body between markers', () => {
        const beats = parseNodeBeats(drama);
        assert.deepEqual(beats.map((beat) => beat.id), ['1', '2']);
        assert.match(beats[0].body, /陆沉推门进来/);
        assert.match(beats[1].title, /Beat 2/);
        assert.doesNotMatch(beats[0].body, /BEAT_START/);
    });

    it('falls back to legacy beat headings', () => {
        const beats = parseNodeBeats('- Beat 3：\n甲出剑。\n~ Beat 4：\n乙侧身。');
        assert.deepEqual(beats.map((beat) => beat.id), ['3', '4']);
        assert.match(beats[0].body, /甲出剑/);
        assert.match(beats[1].body, /乙侧身/);
    });
});

describe('splitStagingBeat', () => {
    it('keeps setup, action, and continuity notes as separate sections', () => {
        const beat = parseNodeBeats(staging)[0];
        const parts = splitStagingBeat(beat.body);
        assert.match(parts.setup, /【建置】/);
        assert.match(parts.setup, /镜头在门内/);
        assert.doesNotMatch(parts.setup, /推门进来/);
        assert.match(parts.play, /【入戏】/);
        assert.match(parts.play, /推门进来/);
        assert.match(parts.notes, /【场记分析】/);
        assert.match(parts.notes, /开拍在场角色数=1/);
        assert.doesNotMatch(parts.notes, /场记分析结束/);
    });
});

describe('buildBeatViewerScenes', () => {
    it('lists scenes, names, and the union of beat ids', () => {
        const scenes = buildBeatViewerScenes({
            EP01_SC02: { drama, staging, combat: '', framing: '' },
            EP01_SC01: {
                drama: '【场景名称】门厅｜夜·内\n- Beat 1：\n有人等候。',
            },
        });
        assert.deepEqual(scenes.map((scene) => scene.sceneId), ['EP01_SC01', 'EP01_SC02']);
        assert.equal(scenes[1].name, '总裁办公室·日·内');
        assert.deepEqual(scenes[1].beatIds, ['1', '2']);
        assert.equal(findNodeBeat(scenes[1].nodes.combat, '1'), null);
        assert.match(findNodeBeat(scenes[1].nodes.staging, '1').body, /场记分析/);
        assert.match(beatOptionLabel(scenes[1], '1'), /开场画面/);
    });

    it('shows an unsplit draft as one block', () => {
        const scenes = buildBeatViewerScenes({
            EP01_SC03: { drama: '【场景名称】走廊\n还没有切拍。' },
        });
        assert.deepEqual(scenes[0].beatIds, [WHOLE_NODE_BEAT_ID]);
        assert.match(findNodeBeat(scenes[0].nodes.drama, WHOLE_NODE_BEAT_ID).body, /还没有切拍/);
    });

    it('fills a missing step from the pipeline block without replacing a stored draft', () => {
        const merged = mergePipelineSceneBlocks(
            { EP01_SC01: { drama: '已有文戏' } },
            [{
                node_name: 'scene_subskill_scene',
                scene_id: 'EP01_SC01',
                runtime_meta: {
                    current_step: 'staging',
                    scene_block: '[BEAT_START:1]\n建置正文\n[BEAT_END:1]',
                },
            }, {
                node_name: 'scene_subskill_scene',
                scene_id: 'EP01_SC04',
                runtime_meta: {
                    called_subskills: ['drama'],
                    scene_block: '- Beat 1：\n管道里的文戏',
                },
            }],
        );
        assert.equal(merged.EP01_SC01.drama, '已有文戏');
        assert.match(merged.EP01_SC01.staging, /建置正文/);
        assert.match(merged.EP01_SC04.drama, /管道里的文戏/);
        const scenes = buildBeatViewerScenes(merged);
        assert.equal(scenes.some((scene) => scene.sceneId === 'EP01_SC04'), true);
    });
});

describe('storyboard beat trace', () => {
    it('reads merged beats from shot logic', () => {
        assert.deepEqual(parseMergedBeatIds('Beat-Shot映射:合镜Beat=Beat1+Beat2｜Duration=11'), ['1', '2']);
        assert.deepEqual(parseMergedBeatIds('合镜Beat=Beat 4｜Duration=5<br>节奏:中'), ['4']);
        assert.deepEqual(parseMergedBeatIds('单Beat=B3｜Duration=2'), ['3']);
        assert.deepEqual(parseMergedBeatIds('合镜=Beat1+Beat2｜Duration=11'), ['1', '2']);
        assert.deepEqual(parseMergedBeatIds('节奏:中｜运镜:MS'), []);
    });

    it('selects the shots that cover a beat and keeps shot order', () => {
        const shots = normalizeStoryboardShots([
            { id: 9, shot_id: 'EP01_SC01_SH02', shot_logic_cn: '合镜Beat=Beat2+Beat3｜Duration=8', video_content: '第二镜' },
            { id: 3, shot_id: 'EP01_SC01_SH01', shot_logic_cn: '合镜Beat=Beat1｜Duration=5', video_content: '第一镜' },
        ]);
        assert.deepEqual(shots.map((shot) => shot.shotId), ['EP01_SC01_SH01', 'EP01_SC01_SH02']);
        assert.deepEqual(shotsCoveringBeat(shots, '2').map((shot) => shot.shotId), ['EP01_SC01_SH02']);
        assert.deepEqual(shotsCoveringBeat(shots, '1').map((shot) => shot.shotId), ['EP01_SC01_SH01']);
    });

    it('shows an unsplit node draft against a beat selected from another node', () => {
        const scenes = buildBeatViewerScenes({
            EP01_SC01: {
                drama: '整段文戏，没有拍标记。',
                staging: '[BEAT_START:1]\n────【建置】────\n建置正文\n[BEAT_END:1]',
            },
        });
        assert.equal(findNodeBeat(scenes[0].nodes.drama, '1')?.body, '整段文戏，没有拍标记。');
        assert.match(findNodeBeat(scenes[0].nodes.staging, '1')?.body, /建置正文/);
    });

    it('keeps earlier node drafts when the live map only has staging', () => {
        const merged = mergeSubskillResultMaps(
            JSON.stringify({
                EP01_SC01: { drama: '文戏', combat: '武戏', framing: '编排', staging: '旧建置' },
            }),
            JSON.stringify({ EP01_SC01: { staging: '新建置' } }),
        );
        assert.equal(merged.EP01_SC01.drama, '文戏');
        assert.equal(merged.EP01_SC01.combat, '武戏');
        assert.equal(merged.EP01_SC01.framing, '编排');
        assert.equal(merged.EP01_SC01.staging, '新建置');
        const chained = mergeSubskillResultMaps(merged, JSON.stringify({
            EP01_SC01: { staging: '再建置' },
        }));
        assert.equal(chained.EP01_SC01.drama, '文戏');
        assert.equal(chained.EP01_SC01.staging, '再建置');
    });

    it('joins drama stored under a scene-number alias with staging on the canonical id', () => {
        const scenes = buildBeatViewerScenes({
            1: { drama: '[BEAT_START:1]\n- Beat 1：\n文戏正文\n[BEAT_END:1]' },
            EP01_SC01: { staging: '[BEAT_START:1]\n────【建置】────\n建置正文\n[BEAT_END:1]' },
        });
        assert.equal(scenes.length, 1);
        assert.equal(scenes[0].sceneId, 'EP01_SC01');
        assert.match(scenes[0].nodes.drama.text, /文戏正文/);
        assert.match(scenes[0].nodes.staging.text, /建置正文/);
    });

    it('matches a workspace scene by scene number', () => {
        const rows = [{ id: 12, scene_no: '3' }, { id: 13, scene_no: 'EP01_SC03A' }];
        assert.equal(matchWorkspaceScene(rows, 'EP01_SC03')?.id, 12);
        assert.equal(matchWorkspaceScene(rows, 'EP01_SC03A')?.id, 13);
    });
});
