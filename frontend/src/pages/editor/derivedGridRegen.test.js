import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
    derivedDependencyImageUrl,
    isCollidingGridCellUrl,
    isGridCropDerivedEntity,
    isSpecialCutDerivedEntity,
    isStateDerivedEntity,
    mainQuadCellAddresses,
    planDerivedGridCell,
    resolveShotReferenceImageUrl,
    quadFailureEnvironmentNames,
    derivedMainRegenHint,
    omitsProjectStyleInjection,
    quadNamesMissingFromResult,
    assembleQuadRerunCandidates,
    mainEnvironmentOpeningDraft,
    extractWrappedDesignDrafts,
    assetProxyFetchUrl,
    readQuadCellImages,
    quadSheetImageUrl,
    entityImageMatchesQuadCell,
    mainEnvironmentDisplayImageUrl,
    singleCellEditInstruction,
    stripProjectStyleInjection,
    applyWhiteModelQuadReference,
    consistencyWhiteModel,
    whiteModelFromConsistencyResult,
    withWhiteModelEditInstruction,
    quadImagePrompt,
    applyQuadProportionLocks,
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

    it('keeps the original four-grid when the stored portrait is the first cell', () => {
        const entity = {
            type: 'environment',
            name: '总裁办',
            image_url: 'https://cdn.example/tl.jpg?e=2',
            custom_attributes: {
                quad_sheet_image_url: 'https://cdn.example/sheet.png?token=old',
                quad_cell_images: {
                    source_url: 'https://cdn.example/sheet.png?token=old',
                    cells: {
                        左上: 'https://cdn.example/tl.jpg',
                        右上: 'https://cdn.example/tr.jpg',
                        左下: 'https://cdn.example/bl.jpg',
                        右下: 'https://cdn.example/br.jpg',
                    },
                },
            },
        };
        assert.equal(quadSheetImageUrl(entity), 'https://cdn.example/sheet.png?token=old');
        assert.equal(entityImageMatchesQuadCell(entity, entity.image_url), true);
        assert.equal(
            mainEnvironmentDisplayImageUrl(entity, entity.image_url),
            'https://cdn.example/sheet.png?token=old',
        );
        assert.equal(
            mainEnvironmentDisplayImageUrl(entity, 'https://cdn.example/new-sheet.png'),
            'https://cdn.example/new-sheet.png',
        );
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
        assert.equal(derivedDependencyImageUrl(stateDerived, main, [main, derived, stateDerived]), 'https://cdn.example/tr.jpg');
    });

    it('does not send the whole four-grid when the matching cell is not saved yet', () => {
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
            generation_prompt_cn: '待生成',
            custom_attributes: { derived_kind: 'first_cut', main_environment: '城门大街', view_angle_from_main: 90 },
            visual_dependencies: ['ENV:[城门大街]'],
        };
        const derivedMain = {
            id: 3,
            type: 'environment',
            name: '城门大街_夜雨',
            custom_attributes: { derived_kind: 'derived_main', source_main_environment: '城门大街' },
            visual_dependencies: ['ENV:[城门大街]'],
        };
        assert.equal(derivedDependencyImageUrl(derived, main, [main, derived]), '');
        assert.equal(derivedDependencyImageUrl(derivedMain, main, [main, derivedMain]), 'https://cdn.example/main.jpg');
    });

    it('treats an existing angled shot as a cell crop even after the cut sentence is gone', () => {
        const main = {
            id: 1,
            type: 'environment',
            name: '泓林土菜馆正门',
            image_url: 'https://cdn.example/quad.jpg',
            generation_prompt_cn: '四宫度数=左上0度｜右上90度｜左下180度｜右下270度',
            custom_attributes: {
                quad_cell_images: {
                    source_url: 'https://cdn.example/quad.jpg',
                    cells: { 左上: 'https://cdn.example/tl.jpg', 右上: 'https://cdn.example/tr.jpg' },
                },
            },
        };
        const derived = {
            id: 2,
            type: 'environment',
            name: '0度泓林土菜馆正门',
            image_url: 'https://cdn.example/current.jpg',
            generation_prompt_cn: '门庭正面。长边横在画面里。',
            visual_dependencies: ['ENV:[泓林土菜馆正门]'],
        };
        const hall = {
            id: 4,
            type: 'environment',
            name: '龙门风月客栈大堂',
            image_url: 'https://cdn.example/hall-quad.jpg',
            generation_prompt_cn: '四宫度数=左上0度｜右上90度｜左下180度｜右下270度',
        };
        const special = {
            id: 3,
            type: 'environment',
            name: '0度龙门风月客栈大堂_仰天',
            image_url: 'https://cdn.example/up.jpg',
            generation_prompt_cn: '所属主环境=龙门风月客栈大堂。angle_key=龙门风月客栈大堂|0。截取宫格=左上0度。禁止只做平视宫格原样切割。特别表述=仰天。',
            custom_attributes: { derived_kind: 'special', main_environment: '龙门风月客栈大堂', view_angle_from_main: 0 },
            visual_dependencies: ['ENV:[龙门风月客栈大堂]'],
        };
        assert.equal(isGridCropDerivedEntity(derived), true);
        assert.equal(isSpecialCutDerivedEntity(derived), false);
        assert.equal(isSpecialCutDerivedEntity(special), true);
        assert.equal(isGridCropDerivedEntity(special), true);
        assert.equal(derivedDependencyImageUrl(derived, main, [main, derived]), 'https://cdn.example/tl.jpg');
        assert.equal(derivedDependencyImageUrl(special, hall, [hall, special]), '');
        const planned = planDerivedGridCell(derived, [main, derived]);
        assert.equal(planned.ok, true);
        assert.equal(planned.position, '左上');
        const specialPlan = planDerivedGridCell(special, [hall, special]);
        assert.equal(specialPlan.ok, true);
        assert.equal(specialPlan.mainEntity.id, 4);
        assert.equal(specialPlan.position, '左上');
    });

    it('uses the current four-grid cell and drops a portrait from the previous sheet', () => {
        const main = {
            id: 1,
            type: 'environment',
            name: '城门大街',
            image_url: 'https://cdn.example/main.jpg',
            generation_prompt_cn: '四宫度数=左上0度｜右上90度｜左下180度｜右下270度',
            custom_attributes: {
                quad_cell_images: {
                    source_url: 'https://cdn.example/main.jpg',
                    cells: { 右上: 'https://cdn.example/tr.jpg' },
                },
            },
        };
        const derived = {
            id: 2,
            type: 'environment',
            name: '90度城门大街',
            image_url: 'https://cdn.example/derived-old.jpg',
            generation_prompt_cn: '只切割。所属主环境=城门大街。angle_key=城门大街|90。',
            custom_attributes: { derived_kind: 'first_cut', main_environment: '城门大街', view_angle_from_main: 90 },
            visual_dependencies: ['ENV:[城门大街]'],
        };
        const character = {
            id: 9,
            type: 'character',
            name: '陆青',
            image_url: 'https://cdn.example/face.jpg',
        };
        assert.equal(resolveShotReferenceImageUrl(derived, [main, derived]), 'https://cdn.example/tr.jpg');
        assert.equal(resolveShotReferenceImageUrl(character, [character]), 'https://cdn.example/face.jpg');

        const rerunMain = {
            ...main,
            image_url: 'https://cdn.example/main-new.jpg',
            custom_attributes: {
                quad_cell_images: {
                    source_url: 'https://cdn.example/main.jpg',
                    cells: { 右上: 'https://cdn.example/tr-old.jpg' },
                },
            },
        };
        const staleDerived = { ...derived, image_url: 'https://cdn.example/tr-old.jpg' };
        assert.equal(resolveShotReferenceImageUrl(staleDerived, [rerunMain, staleDerived]), '');

        const special = {
            id: 3,
            type: 'environment',
            name: '90度城门大街_仰天',
            image_url: 'https://cdn.example/up.jpg',
            generation_prompt_cn: '所属主环境=城门大街。angle_key=城门大街|90。禁止只做平视宫格原样切割。特别表述=仰天。',
            custom_attributes: { derived_kind: 'special', main_environment: '城门大街', view_angle_from_main: 90 },
            visual_dependencies: ['ENV:[城门大街]'],
        };
        assert.equal(resolveShotReferenceImageUrl(special, [main, special]), 'https://cdn.example/up.jpg');
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

describe('main environment quad rerun drafts', () => {
    const opening = '【定位】\n总裁室。\n【六面一次】\n原点=中心。\n【构图】\n平视。';

    it('uses the saved opening when the library card has no prompt body', () => {
        const card = {
            name: '总裁室',
            type: 'environment',
            generation_prompt_cn: null,
            description: opening,
            custom_attributes: { main_environment_opening: opening },
        };
        assert.equal(mainEnvironmentOpeningDraft(card), opening);
        const candidates = assembleQuadRerunCandidates({
            entities: [{
                name: '总裁室',
                prompt: '',
                opening,
                fromDesign: true,
                hasQuad: false,
            }],
            planRows: [{
                name: '总裁室',
                prompt: '',
                opening: '【主环境】总裁室\n【活动空间】出入画口=大门',
                fromDesign: false,
            }],
        });
        assert.equal(candidates.length, 1);
        assert.equal(candidates[0].fromDesign, true);
        assert.equal(candidates[0].opening, opening);
    });

    it('joins a design whose name has a bar suffix to the plan name', () => {
        const candidates = assembleQuadRerunCandidates({
            designRows: [{
                name: '总裁室｜奢华',
                prompt: opening,
                opening,
                fromDesign: true,
                hasQuad: false,
            }],
            planRows: [{
                name: '总裁室',
                prompt: '',
                opening: '【主环境】总裁室',
                fromDesign: false,
            }],
        });
        assert.equal(candidates.length, 1);
        assert.match(candidates[0].opening, /【六面一次】/);
    });

    it('does not offer a plan outline that has no design draft', () => {
        const candidates = assembleQuadRerunCandidates({
            planRows: [{
                name: '总裁室',
                prompt: '',
                opening: '【主环境】总裁室\n【活动空间】出入画口=大门',
                fromDesign: false,
            }],
        });
        assert.deepEqual(candidates, []);
    });

    it('reads a wrapped design block', () => {
        const drafts = extractWrappedDesignDrafts(`【主环境设计稿】总裁室\n${opening}\n【/主环境设计稿】`);
        assert.equal(drafts.length, 1);
        assert.equal(drafts[0].name, '总裁室');
        assert.match(drafts[0].generation_prompt_cn, /【六面一次】/);
    });
});

describe('quad image prompt', () => {
    const draft = [
        '[Global Style](写实电影感).',
        '【四向拼图】',
        '[0度格-左上·北]',
        '正面：墙。',
        '【主体外形】',
        '- [@保险台]（M-001）外形=实心台体，颜色=深青哑光。',
        '【色彩说明】',
        '- 主色=深青冷灰。https://cdn.example/sheet.png?sig=1',
        '【主体外形】',
        '- [@保险台]（M-001）外形=实心台体，颜色=深青哑光。',
        '【色彩说明】',
        '- 主色=深青冷灰。https://cdn.example/sheet.png?sig=1',
    ].join('\n');

    it('keeps the material table once after the four-grid and drops image urls', () => {
        const prompt = quadImagePrompt(draft);
        assert.equal(prompt.indexOf('【四向拼图】') < prompt.indexOf('【主体外形】'), true);
        assert.equal(prompt.indexOf('【主体外形】') < prompt.indexOf('【色彩说明】'), true);
        assert.equal(prompt.match(/【主体外形】/g).length, 1);
        assert.equal(prompt.match(/【色彩说明】/g).length, 1);
        assert.match(prompt, /^\[Global Style\]\(写实电影感\)\./);
        assert.match(prompt, /\[0度格-左上·北\]/);
        assert.doesNotMatch(prompt, /https?:\/\//);
        assert.match(prompt, /主色=深青冷灰。/);
    });
});

describe('locked quad proportions', () => {
    const cells = [
        '[0度格-左上·北]',
        '正面：远处那一整面是[@铆接冷轧钢板墙皮]（N-001），[@双联密锁防爆壁柜]（N-002）都在这张墙上。同面序在中段，两端不到画面边缘。本格没有门。',
        '中部：[@保险台]（M-001）靠近镜头的是宽的一面。这一面左右宽、往后窄，左右两端外面还看得见地面。',
        '[90度格-右上·东]',
        '正面：远处那一整面是[@无缝冷轧钢板墙皮]（E-001）。台仍是左右窄、往后长。本格没有门。',
        '中部：[@保险台]（M-001）靠近镜头的是窄的一面。这一面左右窄、往后长，左右两边外面还看得见地面。',
        '[180度格-左下·南]',
        '正面：远处那一整面是[@拼缝冷轧钢板墙皮]（S-001），[@防爆金属门]（S-002）都在这张墙上。这扇门的宽度大约只有这面墙的四分之一。本格的门只有上面点到的。',
        '中部：[@保险台]（M-001）靠近镜头的是宽的一面。这一面左右宽、往后窄，左右是往后的两倍，左右两端外面还看得见地面。',
        '[270度格-右下·西]',
        '正面：远处那一整面是[@加厚冷轧钢板墙皮]（W-001）。台仍是左右只有往后的一半。本格没有门。',
        '中部：[@保险台]（M-001）靠近镜头的是窄的一面。这一面左右窄、往后长，左右只有往后的一半，左右两边外面还看得见地面。',
        '【主体外形】',
        '[@保险台]（M-001）外形=实心台体。',
    ].join('\n');

    const boxes = [
        { name: '铆接冷轧钢板墙皮', kind: 'wall', east: 0, north: 3.75, along_east: 6.5, along_north: 0.2, height: 2.9 },
        { name: '双联密锁防爆壁柜', kind: 'furniture', east: 0, north: 3.55, along_east: 3.0, along_north: 0.4, height: 2.0 },
        { name: '拼缝冷轧钢板墙皮', kind: 'wall', east: 0, north: -3.75, along_east: 6.5, along_north: 0.2, height: 2.9 },
        { name: '防爆金属门', kind: 'door', east: 0, north: -3.75, along_east: 1.0, along_north: 0.2, height: 2.9 },
        { name: '保险台', kind: 'furniture', east: 0, north: 0, along_east: 1.8, along_north: 0.9, height: 0.75 },
    ];

    const opening = [
        '【六面一次】',
        '[@保险台]号=#4｜长边平行=X线｜占地=1.8×0.9米。',
        '【北壁】',
        '尺度=开间6.5米×高2.9米。双联密锁防爆壁柜号=#6｜壁关系=贴墙｜占地=沿墙3.0米×高2.0米×厚0.40米。',
        '【南壁】',
        '尺度=开间6.5米×高2.9米。防爆金属门号=#10｜壁关系=门洞｜占地=沿墙1.0米×高2.9米×厚0.20米。',
    ].join('\n');

    function southDoor(prompt) {
        const at = prompt.indexOf('[180度格');
        return prompt.slice(at, prompt.indexOf('[270度格'));
    }

    it('follows the white-model boxes when they exist', () => {
        const prompt = applyQuadProportionLocks(cells, {
            type: 'environment',
            custom_attributes: { layout_boxes: boxes },
            description: opening.replace('1.0米', '4.0米'),
        });
        assert.match(southDoor(prompt), /这扇门的宽度大约只有这面墙的八分之一。/);
        assert.doesNotMatch(prompt, /四分之一/);
        assert.match(prompt, /\[@双联密锁防爆壁柜\]的沿墙长大约只有这面墙的一半。/);
        assert.equal(prompt.indexOf('沿墙长大约只有') < prompt.indexOf('[90度格'), true);
        assert.match(prompt.slice(prompt.indexOf('[0度格'), prompt.indexOf('[90度格')), /左右是往后的两倍/);
        assert.match(prompt.slice(prompt.indexOf('[90度格'), prompt.indexOf('[180度格')), /左右只有往后的一半/);
        assert.match(prompt, /【主体外形】\n\[@保险台\]/);
    });

    it('uses the opening meters when no white model exists', () => {
        const prompt = applyQuadProportionLocks(cells, {
            type: 'environment',
            description: opening,
        });
        assert.match(southDoor(prompt), /八分之一/);
        assert.match(prompt, /\[@双联密锁防爆壁柜\]的沿墙长大约只有这面墙的一半。/);
    });

    it('drops the double phrase when the table is shorter than one and a half', () => {
        const prompt = applyQuadProportionLocks(cells, {
            type: 'environment',
            custom_attributes: {
                layout_boxes: boxes.map((box) => (box.name === '保险台' ? { ...box, along_east: 1.2, along_north: 1.0 } : box)),
            },
        });
        assert.doesNotMatch(prompt, /左右是往后的两倍/);
        assert.doesNotMatch(prompt, /左右只有往后的一半/);
        assert.match(prompt, /台仍是左右窄、往后长。/);
    });
});

describe('white model reference for the four-grid', () => {
    it('puts the clay sheet first and keeps color in the written prompt', () => {
        const entity = {
            custom_attributes: { layout_image_url: 'https://cdn.example/clay.png' },
        };
        const applied = applyWhiteModelQuadReference(
            '【主体外形】青砖墙。\n【四向拼图】左上望北。',
            ['https://cdn.example/style.png', 'https://cdn.example/clay.png'],
            entity
        );
        assert.match(applied.prompt, /^朝向参考：第一张参考图是这一处的白模四宫/);
        assert.doesNotMatch(applied.prompt, /占画面的比例照这张白模/);
        assert.match(applied.prompt, /朝向边上的短划只标这一面/);
        assert.match(applied.prompt, /颜色、材质、纹样、光线和光比按后面的文字/);
        assert.match(applied.prompt, /【主体外形】青砖墙/);
        assert.deepEqual(applied.refs, [
            'https://cdn.example/clay.png',
            'https://cdn.example/style.png',
        ]);
    });

    it('replaces an older lock instruction with the weak reference', () => {
        const entity = {
            custom_attributes: { layout_image_url: 'https://cdn.example/clay.png' },
        };
        const applied = applyWhiteModelQuadReference(
            '第一张参考图是同一处的白模，只锁四格切分和每一具的体块。\n\n【四向拼图】左上望北。',
            [],
            entity
        );
        assert.match(applied.prompt, /^朝向参考：/);
        assert.doesNotMatch(applied.prompt, /只锁四格/);
        assert.match(applied.prompt, /【四向拼图】左上望北/);
    });

    it('leaves the prompt and refs unchanged when no white model exists', () => {
        const applied = applyWhiteModelQuadReference('【四向拼图】', ['https://cdn.example/a.png'], {});
        assert.equal(applied.prompt, '【四向拼图】');
        assert.deepEqual(applied.refs, ['https://cdn.example/a.png']);
    });
});

describe('white model facing check', () => {
    const main = {
        id: 3,
        type: 'environment',
        name: '厨房',
        image_url: 'https://cdn.example/kitchen.png',
        custom_attributes: { layout_image_url: 'https://cdn.example/clay.png' },
    };

    it('uses the asset white model for a four-grid check', () => {
        const found = consistencyWhiteModel(main, [main]);
        assert.deepEqual(found, {
            url: 'https://cdn.example/clay.png',
            scope: 'quad',
            position: '',
        });
    });

    it('uses the owning main white model and names the cell', () => {
        const cell = {
            id: 9,
            type: 'environment',
            name: '90度厨房',
            image_url: 'https://cdn.example/cell.png',
            custom_attributes: {
                derived_kind: 'first_cut',
                view_angle_from_main: 90,
                main_environment: '厨房',
            },
        };
        const found = consistencyWhiteModel(cell, [main, cell]);
        assert.equal(found.url, 'https://cdn.example/clay.png');
        assert.equal(found.scope, 'sheet');
        assert.equal(found.position, '右上');
    });

    it('falls back to the source main when a derived main has no white model', () => {
        const source = {
            id: 1,
            type: 'environment',
            name: '办公室',
            custom_attributes: { layout_image_url: 'https://cdn.example/office-clay.png' },
        };
        const derived = {
            id: 2,
            type: 'environment',
            name: '办公室_破损',
            custom_attributes: { derived_kind: 'derived_main', source_main_environment: '办公室' },
        };
        const found = consistencyWhiteModel(derived, [source, derived]);
        assert.equal(found.url, 'https://cdn.example/office-clay.png');
        assert.equal(found.scope, 'quad');
    });

    it('returns nothing when no white model is stored', () => {
        assert.equal(consistencyWhiteModel({ type: 'environment', name: '厨房' }, []), null);
    });

    it('reads the white model generated by a consistency check', () => {
        assert.deepEqual(whiteModelFromConsistencyResult({
            white_model_url: 'https://cdn.example/clay.png',
            white_model_scope: 'sheet',
            white_model_position: '右上',
            white_model_entity_id: 3,
        }), {
            url: 'https://cdn.example/clay.png',
            scope: 'sheet',
            position: '右上',
            entityId: '3',
        });
        assert.equal(whiteModelFromConsistencyResult({}), null);
    });

    it('names the cell, the subject, and the change before the white-model note', () => {
        const body = '改右上格的办公沙发。靠近镜头的是窄的一面。长边从靠近镜头伸向远离镜头，短边朝画面左右。改右下格的金属滑移门。这一格正对这具。全关。';
        const quad = withWhiteModelEditInstruction(body, {
            url: 'https://cdn.example/clay.png',
            scope: 'quad',
        });
        assert.match(quad, /^改右上格的办公沙发/);
        assert.equal(quad.includes('每一具'), false);
        assert.equal(quad.includes('都跟对应格'), false);
        assert.match(quad, /长边从靠近镜头伸向远离镜头，短边朝画面左右/);
        assert.match(quad, /改右下格的金属滑移门/);
        assert.match(quad, /白模的白底/);
        assert.ok(quad.indexOf('改右上格的办公沙发') < quad.indexOf('第一张是要改的原图'));
        assert.equal(withWhiteModelEditInstruction(quad, { url: 'https://cdn.example/clay.png', scope: 'quad' }), quad);
        const cell = withWhiteModelEditInstruction('改右上格的门。这一格正对这具。全关。', {
            url: 'https://cdn.example/clay.png',
            scope: 'sheet',
            position: '右上',
        });
        assert.match(cell, /^改右上格的门/);
        assert.match(cell, /已经裁出的右上格/);
        assert.match(cell, /不要把另外三格画回来/);
        assert.equal(cell.includes('都跟这一格'), false);
        assert.equal(withWhiteModelEditInstruction('改门。', null), '改门。');
    });
});

describe('asset proxy fetch url', () => {
    it('routes remote sheets through the API proxy and leaves local paths alone', () => {
        assert.equal(
            assetProxyFetchUrl('https://cdn.example/sheet.png?token=a b', '/api/v1'),
            '/api/v1/assets/proxy?url=https%3A%2F%2Fcdn.example%2Fsheet.png%3Ftoken%3Da%20b'
        );
        assert.equal(assetProxyFetchUrl('/uploads/3/sheet.jpg', '/api/v1'), '');
        assert.equal(assetProxyFetchUrl('blob:http://127.0.0.1/abc', '/api/v1'), '');
        assert.equal(
            assetProxyFetchUrl('/api/v1/assets/proxy?url=https%3A%2F%2Fcdn.example%2Fa.jpg', '/api/v1'),
            '/api/v1/assets/proxy?url=https%3A%2F%2Fcdn.example%2Fa.jpg'
        );
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
