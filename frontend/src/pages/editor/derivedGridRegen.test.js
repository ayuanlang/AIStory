import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
    derivedDependencyImageUrl,
    isCollidingGridCellUrl,
    isGridCropDerivedEntity,
    isStateDerivedEntity,
    mainQuadCellAddresses,
    planDerivedGridCell,
    quadFailureEnvironmentNames,
    derivedMainRegenHint,
    omitsProjectStyleInjection,
    quadNamesMissingFromResult,
    readQuadCellImages,
    singleCellEditInstruction,
    stripProjectStyleInjection,
} from './derivedGridRegen.js';

describe('saved quad cells', () => {
    it('returns the four saved cells only when they belong to the current main image', () => {
        const entity = {
            custom_attributes: {
                quad_cell_images: {
                    source_url: 'https://cdn.example/main.jpg',
                    cells: {
                        左上: 'https://cdn.example/tl.jpg',
                        右上: 'https://cdn.example/tr.jpg',
                        左下: '',
                        右下: 'https://cdn.example/br.jpg',
                    },
                },
            },
        };
        assert.deepEqual(readQuadCellImages(entity, 'https://cdn.example/main.jpg'), {
            左上: 'https://cdn.example/tl.jpg',
            右上: 'https://cdn.example/tr.jpg',
            右下: 'https://cdn.example/br.jpg',
        });
        assert.equal(readQuadCellImages(entity, 'https://cdn.example/other.jpg'), null);
        assert.deepEqual(readQuadCellImages(entity, 'https://cdn.example/main.jpg?e=2&token=new'), {
            左上: 'https://cdn.example/tl.jpg',
            右上: 'https://cdn.example/tr.jpg',
            右下: 'https://cdn.example/br.jpg',
        });
        assert.deepEqual(readQuadCellImages(entity, 'https://cdn.example/other.jpg', { allowStale: true }), {
            左上: 'https://cdn.example/tl.jpg',
            右上: 'https://cdn.example/tr.jpg',
            右下: 'https://cdn.example/br.jpg',
        });
        const stringified = {
            custom_attributes: {
                quad_cell_images: JSON.stringify({
                    source_url: 'https://cdn.example/main.jpg',
                    cells: {
                        左上: '{"url":"https://cdn.example/tl.jpg"}',
                        右上: 'https://cdn.example/tr.jpg',
                    },
                }),
            },
        };
        assert.deepEqual(readQuadCellImages(stringified, 'https://cdn.example/main.jpg'), {
            左上: 'https://cdn.example/tl.jpg',
            右上: 'https://cdn.example/tr.jpg',
        });
    });

    it('turns a quad edit instruction into a single-cell edit', () => {
        const text = singleCellEditInstruction(
            '改0度格的城墙。现在接到天际。改成接到城门楼。只改这一格里点名的这一处。另外三格、格线、角标、没有点名的主体、光色和构图都保持原图不动。不要重画整张四宫。'
        );
        assert.match(text, /已经裁出的单格画面/);
        assert.doesNotMatch(text, /不要重画整张四宫/);
        assert.match(text, /改0度格的城墙/);
    });

    it('plans the matching cell without a grid-cell prompt', () => {
        const main = {
            id: 1,
            type: 'environment',
            name: '城门大街',
            image_url: 'https://cdn.example/main.jpg',
            generation_prompt_cn: '四宫度数=左上0度｜右上90度｜左下180度｜右下270度',
        };
        const derived = {
            id: 2,
            type: 'environment',
            name: '90度城门大街',
            generation_prompt_cn: '只切割。所属主环境=城门大街。angle_key=城门大街|90。',
            custom_attributes: { derived_kind: 'first_cut', main_environment: '城门大街' },
        };
        const plan = planDerivedGridCell(derived, [main, derived]);
        assert.equal(plan.ok, true);
        assert.equal(plan.position, '右上');
        assert.equal(plan.angle, '90');
        assert.equal(plan.mainEntity.id, 1);
    });

    it('crops a state angle from the derived main, not the original main', () => {
        const source = {
            id: 1,
            type: 'environment',
            name: '客栈大堂',
            image_url: 'https://cdn.example/source.jpg',
            generation_prompt_cn: '四宫度数=左上0度｜右上90度｜左下180度｜右下270度',
        };
        const derivedMain = {
            id: 2,
            type: 'environment',
            name: '客栈大堂_破洞',
            image_url: 'https://cdn.example/broken.jpg',
            generation_prompt_cn: '四宫度数=左上0度｜右上90度｜左下180度｜右下270度',
            custom_attributes: { derived_kind: 'derived_main', source_main_environment: '客栈大堂' },
        };
        const angle = {
            id: 3,
            type: 'environment',
            name: '90度客栈大堂_破洞',
            generation_prompt_cn: '待生成',
            visual_dependencies: ['ENV:[客栈大堂]'],
            custom_attributes: {
                derived_kind: 'first_cut',
                derived_from_state: true,
                main_environment: '客栈大堂_破洞',
                derived_main_environment: '客栈大堂_破洞',
                source_main_environment: '客栈大堂',
                view_angle_from_main: 90,
            },
        };
        const plan = planDerivedGridCell(angle, [source, derivedMain, angle]);
        assert.equal(plan.ok, true);
        assert.equal(plan.mainEntity.id, 2);
        assert.equal(plan.position, '右上');
    });

    it('uses the derived main cell when the stored dependency still names the original', () => {
        const cellsOf = (url, cellUrl) => ({
            source_url: url,
            cells: { 左上: `${cellUrl}-tl`, 右上: `${cellUrl}-tr`, 左下: `${cellUrl}-bl`, 右下: `${cellUrl}-br` },
        });
        const source = {
            id: 1,
            type: 'environment',
            name: '客栈大堂',
            image_url: 'https://cdn.example/source.jpg',
            generation_prompt_cn: '四宫度数=左上0度｜右上90度｜左下180度｜右下270度。正面：完好东窗。',
            custom_attributes: { quad_cell_images: cellsOf('https://cdn.example/source.jpg', 'https://cdn.example/source') },
        };
        const derivedMain = {
            id: 2,
            type: 'environment',
            name: '客栈大堂_破洞',
            image_url: 'https://cdn.example/broken.jpg',
            generation_prompt_cn: '四宫度数=左上0度｜右上90度｜左下180度｜右下270度。正面：破洞东窗。',
            custom_attributes: {
                derived_kind: 'derived_main',
                source_main_environment: '客栈大堂',
                quad_cell_images: cellsOf('https://cdn.example/broken.jpg', 'https://cdn.example/broken'),
            },
        };
        const angle = {
            id: 3,
            type: 'environment',
            name: '90度客栈大堂_破洞',
            generation_prompt_cn: '待生成',
            visual_dependencies: ['ENV:[客栈大堂]'],
            custom_attributes: {
                derived_kind: 'first_cut',
                main_environment: '客栈大堂',
                view_angle_from_main: 90,
            },
        };
        const plan = planDerivedGridCell(angle, [source, derivedMain, angle]);
        assert.equal(plan.ok, true);
        assert.equal(plan.mainEntity.id, 2);
        assert.equal(plan.position, '右上');
        assert.equal(
            derivedDependencyImageUrl(angle, source, [source, derivedMain, angle]),
            'https://cdn.example/broken-tr',
        );
    });

    it('lists saved cell addresses and points a first cut at its cell', () => {
        const main = {
            id: 1,
            type: 'environment',
            name: '城门大街',
            image_url: 'https://cdn.example/main.jpg',
            generation_prompt_cn: '四宫度数=左上0度｜右上90度｜左下180度｜右下270度',
            custom_attributes: {
                quad_cell_images: {
                    source_url: 'https://cdn.example/main.jpg',
                    cells: {
                        左上: 'https://cdn.example/tl.jpg',
                        右上: 'https://cdn.example/tr.jpg',
                        左下: 'https://cdn.example/bl.jpg',
                        右下: 'https://cdn.example/br.jpg',
                    },
                },
            },
        };
        const derived = {
            id: 2,
            type: 'environment',
            name: '90度城门大街',
            image_url: 'https://cdn.example/derived.jpg',
            generation_prompt_cn: '只切割。所属主环境=城门大街。angle_key=城门大街|90。',
            custom_attributes: { derived_kind: 'first_cut', main_environment: '城门大街' },
            visual_dependencies: ['ENV:[城门大街]'],
        };
        const stateDerived = {
            id: 3,
            type: 'environment',
            name: '90度城门大街_夜雨',
            generation_prompt_cn: '以已切割的同角衍生「90度城门大街」参考图为本镜头最终画面。不要重切宫格。',
            custom_attributes: { derived_kind: 'state' },
            image_url: '',
        };
        assert.deepEqual(mainQuadCellAddresses(main).map((row) => `${row.position}${row.degree}`), [
            '左上0',
            '右上90',
            '左下180',
            '右下270',
        ]);
        assert.equal(derivedDependencyImageUrl(derived, main, [main, derived]), 'https://cdn.example/tr.jpg');
        const refreshedMain = { ...main, image_url: 'https://cdn.example/main.jpg?e=9&token=refreshed' };
        assert.equal(derivedDependencyImageUrl(derived, refreshedMain, [refreshedMain, derived]), 'https://cdn.example/tr.jpg');
        assert.equal(isStateDerivedEntity(stateDerived), true);
        assert.equal(isGridCropDerivedEntity(stateDerived), false);
        assert.equal(derivedDependencyImageUrl(stateDerived, derived, [main, derived, stateDerived]), 'https://cdn.example/derived.jpg');
        assert.equal(derivedDependencyImageUrl(stateDerived, main, [main, derived, stateDerived]), 'https://cdn.example/main.jpg');
    });

    it('reads named four-grid gaps and leaves library misses out of the rerun list', () => {
        const detail = (
            'ENVIRONMENT_QUAD_NOT_APPLIED: 四宫格未写回全部主环境。主环境6条，提示词合格5条，已写入0条。'
            + '提示词缺标记：城北生鲜冷链仓库缺[270度格-右下。'
            + '请求里的设计稿未一次写回：城北生鲜冷链仓库、城北废弃变电站、七号地下工业堡垒、七号堡垒外围废墟。'
        );
        assert.deepEqual(quadFailureEnvironmentNames(detail), {
            names: ['城北生鲜冷链仓库', '城北废弃变电站', '七号地下工业堡垒', '七号堡垒外围废墟'],
            unmatched: [],
            truncated: false,
        });
        const truncated = quadFailureEnvironmentNames(
            '提示词缺标记：甲缺【四向拼图】、[0度格-左上；乙缺[270度格-右下；另有2条。请求里的设计稿未一次写回：甲、乙等4条。'
        );
        assert.deepEqual(truncated.names, ['甲', '乙']);
        assert.equal(truncated.truncated, true);
        const libraryMiss = quadFailureEnvironmentNames('库中无同名环境：地下军械库。');
        assert.deepEqual(libraryMiss.names, []);
        assert.deepEqual(libraryMiss.unmatched, ['地下军械库']);
        assert.deepEqual(quadFailureEnvironmentNames('四宫格未写回：结果里没有可写回的主环境。').names, []);
        assert.deepEqual(quadFailureEnvironmentNames('四宫格未一次写满：客栈大堂、天台。').names, ['客栈大堂', '天台']);
    });

    it('treats one ready four-grid as the one requested environment', () => {
        const cells = [
            '【四向拼图】',
            '[0度格-左上·北]',
            '[90度格-右上·东]',
            '[180度格-左下·南]',
            '[270度格-右下·西]',
        ].join('\n');
        const parsed = { environments: [{ name: '0度客栈大堂', generation_prompt_cn: cells }] };
        assert.deepEqual(quadNamesMissingFromResult(parsed, ['客栈大堂']), []);
        assert.deepEqual(quadNamesMissingFromResult(parsed, ['客栈大堂', '天台']), ['客栈大堂', '天台']);
        const spaced = { environments: [{ name: '客栈 大堂｜室内', generation_prompt_cn: cells }] };
        assert.deepEqual(quadNamesMissingFromResult(spaced, ['客栈大堂', '天台']), ['天台']);
    });

    it('drops shared grid-cell filenames so another project image is not reused', () => {
        const shared = 'https://qn.woola.fun/aistory/upload/202610/3/uploads/grid-cell-%E5%B7%A6%E4%B8%8A.jpg?e=1&token=abc';
        assert.equal(isCollidingGridCellUrl(shared), true);
        assert.equal(isCollidingGridCellUrl('https://cdn.example/grid-cell-tl-m5k2-ab12.jpg'), false);
        const entity = {
            image_url: 'https://cdn.example/main.jpg',
            custom_attributes: {
                quad_cell_images: {
                    source_url: 'https://cdn.example/main.jpg',
                    cells: {
                        左上: shared,
                        右上: 'https://cdn.example/grid-cell-tr-unique.jpg',
                    },
                },
            },
        };
        assert.deepEqual(readQuadCellImages(entity, 'https://cdn.example/main.jpg'), {
            右上: 'https://cdn.example/grid-cell-tr-unique.jpg',
        });
    });
});

describe('derived main regen hint', () => {
    it('recovers the source four-grid dependency after the design prompt was copied', () => {
        const source = { type: 'environment', name: '客栈大堂', generation_prompt_cn: '【四向拼图】' };
        const wiped = { type: 'environment', name: '客栈大堂_破损', generation_prompt_cn: '【四向拼图】整间照抄' };
        const child = {
            type: 'environment',
            name: '0度客栈大堂_破损',
            custom_attributes: {
                derived_from_state: true,
                derived_main_environment: '客栈大堂_破损',
                source_main_environment: '客栈大堂',
                state_delta: '南壁破了一个洞',
            },
        };
        assert.deepEqual(derivedMainRegenHint(wiped, [source, wiped, child]), {
            name: '客栈大堂_破损',
            source: '客栈大堂',
            delta: '南壁破了一个洞',
        });
        assert.equal(derivedMainRegenHint(source, [source, wiped, child]), null);
    });
});

describe('derived environment generation prompt', () => {
    it('drops project style and keeps the main-environment delta', () => {
        const derived = {
            type: 'environment',
            name: '客栈大堂_破损',
            custom_attributes: { derived_kind: 'derived_main', source_main_environment: '客栈大堂' },
        };
        const main = { type: 'environment', name: '客栈大堂', custom_attributes: {} };
        assert.equal(omitsProjectStyleInjection(derived), true);
        assert.equal(omitsProjectStyleInjection(main), false);
        const prompt = '[Global Style](暖调院线写实). 衍生主环境=客栈大堂_破损。被依赖主环境=客栈大堂。状态Delta=南壁破了一个洞。';
        assert.equal(
            stripProjectStyleInjection(prompt),
            '衍生主环境=客栈大堂_破损。被依赖主环境=客栈大堂。状态Delta=南壁破了一个洞。'
        );
    });
});
