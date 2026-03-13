# KIE 枚举值统一标准与映射总结

- 标准维度数: 17
- 标准值总数: 285
- 映射关系总数: 739

## 标准维度覆盖
- ASPECT_RATIO: 10 个标准值, 144 条映射
- CHARACTER_ORIENTATION: 2 个标准值, 2 条映射
- DURATION_SECONDS: 14 个标准值, 80 条映射
- IMAGE_SIZE_CLASS: 1 个标准值, 8 条映射
- MODE: 5 个标准值, 8 条映射
- MODEL_ID: 79 个标准值, 80 条映射
- MULTI_SHOTS_SUPPORTED: 1 个标准值, 2 条映射
- NUM_IMAGES: 4 个标准值, 24 条映射
- OUTPUT_FORMAT: 2 个标准值, 8 条映射
- QUALITY_LEVEL: 3 个标准值, 8 条映射
- REASONING_EFFORT: 2 个标准值, 10 条映射
- RESOLUTION_TIER: 9 个标准值, 66 条映射
- SAFETY_TOLERANCE: 7 个标准值, 7 条映射
- SOUND_SUPPORTED: 2 个标准值, 3 条映射
- STYLE: 5 个标准值, 13 条映射
- UPSCALE_FACTOR: 4 个标准值, 7 条映射
- VOICE_ID: 135 个标准值, 269 条映射

## 关键同义归一示例
- ASPECT_RATIO: portrait -> 9:16, landscape -> 16:9
- MODE: std/standard -> STANDARD
- RESOLUTION_TIER: 720p -> P720, 1080p -> P1080, 1k -> K1

## 产物文件
- _kie_system_data_standard_dictionary.csv: 系统统一数据标准字典
- _kie_system_to_model_enum_mapping.csv: 标准与模型字段枚举值映射关系
- _kie_system_data_standard_summary.md: 本总结