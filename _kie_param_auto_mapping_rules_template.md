# KIE 参数自动匹配模板（比例+清晰度）

## 目标
- 用户只需要选择两个主参数：比例（ratio）和清晰度（quality）。
- 系统根据模型能力画像，自动映射到具体 API 字段。

## 文件
- _kie_model_capability_profiles_template.csv: 定义模型支持哪类字段组合。
- _kie_param_auto_mapping_rules_template.csv: 定义不同画像下的映射规则与回退策略。

## 推荐运行逻辑
1. 输入: model_key, source_ratio, source_quality。
2. 识别模型所属 profile_code。
3. 查询规则表，按 priority 升序匹配有效规则。
4. 生成 target_field/target_value 参数集合。
5. 若字段或值不支持，执行 fallback_action。

## fallback_action 建议语义
- fail_if_not_supported: 直接返回不可满足，提示换模型或改参数。
- degrade_quality_to_1080p: 自动降档到可用分辨率。
- degrade_quality_to_1k: 自动降到 1k。
- map_to_nearest_size: 将 ratio 映射到最近 size 枚举。
- keep_square_and_warn_ratio_conflict: 固定 square，并提示比例冲突。
- use_model_default: 不下发该字段，使用模型默认值。

## 示例
- 用户选择 9:16 + 2k:
  - P1 模型 -> aspect_ratio=9:16, resolution=2k
  - P2 模型 -> aspect_ratio=9:16, image_resolution=2k
  - P5 模型 -> image_size=square, image_resolution=2k（并提示比例冲突）

## 与现有入库文件关系
- 字段定义来源: _kie_input_param_field_dim_for_db.csv
- 枚举事实来源: _kie_input_param_enum_values_for_db.csv
- 本模板是上层决策规则，可单独建表并关联 model_key/profile_code。
