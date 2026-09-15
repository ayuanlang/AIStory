# SKILL: promo_generation

## Name
Promo Planner (商业宣传片智能策划)

## Purpose
作为独立 skill 提交后，一次性输出可落地的**整体方案**：内容模式与内容大纲、视频表现形式、各平台策略；允许「单片全案 / 主片+平台改编 / 系列组合」三种组合模式。

## Prompt Source
- 主提示词：`skills/promo_generation/promo_planner_scheme.md`
- 视觉解析（可选前置）：`skills/promo_generation/promo_planner_image_analysis.md`
- 成片剧本：`skills/promo_generation/promo_planner_script.md`
- 执行器：`app.services.promo_planner.generate_promo_planner_scheme` / `generate_promo_script`
- 注册入口：`skills/skills_registry.json` 中 `id = promo_generation`

## Runtime
1. 用户锁定 `goal_type`（必填）；叙事、表现形式、平台可空，由本 skill 回填。
2. 有图片则先跑视觉解析，再一次性生成整体方案 JSON。
3. 用户锁定项原样写入主片，不得改判；系列辅片可以换类型，但须写清与主片的配合关系。
4. 「成片脚本方向预览」可再生成正式成片剧本，写入同账户剧本项目的分集 `script_content`（剧本页）。

## Notes
- 项目只代表单次宣传目标；企业 / 品牌 / 产品与服务是可复用主体。
- 不编造用户未提供的事实；缺口写入 `missing_info_diagnosis`。
- 对标禁止抄袭具体成片桥段 / 文案 / 镜头。
