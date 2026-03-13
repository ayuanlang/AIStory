# KIE 系统字典 -> API 枚举映射覆盖报告

- API 枚举源文件: _kie_input_param_enum_values_for_db.csv
- 系统字典源文件: _kie_system_data_standard_dictionary.csv
- 排除维度: MODEL_ID, VOICE_ID
- 反向映射产物: _kie_standard_to_api_enum_mapping.csv
- 总映射行数: 1110

## 维度覆盖率
- ASPECT_RATIO: 310/310 (100.00%)
- CHARACTER_ORIENTATION: 2/2 (100.00%)
- DURATION_SECONDS: 434/434 (100.00%)
- IMAGE_SIZE_CLASS: 8/8 (100.00%)
- MODE: 15/15 (100.00%)
- NUM_IMAGES: 24/24 (100.00%)
- OUTPUT_FORMAT: 8/8 (100.00%)
- QUALITY_LEVEL: 12/12 (100.00%)
- REASONING_EFFORT: 10/10 (100.00%)
- RESOLUTION_TIER: 252/252 (100.00%)
- SAFETY_TOLERANCE: 7/7 (100.00%)
- STYLE: 20/20 (100.00%)
- UPSCALE_FACTOR: 8/8 (100.00%)

- 全局覆盖率: 1110/1110 (100.00%)

## 规则分布
- exact: 190
- fallback_baseline: 344
- fallback_min: 90
- nearest_lower: 383
- nearest_ratio: 102
- semantic_alias: 1