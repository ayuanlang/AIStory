import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
    planDerivedGridCell,
    readQuadCellImages,
    singleCellEditInstruction,
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
});
