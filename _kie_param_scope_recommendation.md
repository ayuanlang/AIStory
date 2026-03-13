# KIE 入参分层建议（按最新口径）

## 分层原则
- 保留 `paths.post.input.output_format` 与 `paths.post.input.mode` 在 Settings。
- `mode` 采用 model 绑定策略：按 `provider+model -> default_mode` 配置，不作为 provider 级单一全局值。
- 其余字段归到项目设置。
- 当前策略下不启用分镜层参数覆盖。

## 覆盖优先级
项目设置 > Settings > 模型默认值

## 字段归属建议（基于当前 KIE 枚举字段）

### 1) Settings
- paths.post.input.mode
- paths.post.input.output_format

### 2) 项目设置（其余全部）
- paths.post.model
- paths.post.input.quality
- paths.post.input.style
- paths.post.input.safety_tolerance
- paths.post.input.voice
- paths.post.reasoning_effort
- paths.post.input.aspect_ratio
- paths.post.input.resolution
- paths.post.input.size
- paths.post.input.image_resolution
- paths.post.input.image_size
- paths.post.input.upscale_factor
- paths.post.input.character_orientation
- paths.post.input.duration
- paths.post.input.n_frames
- paths.post.input.num_images

## 对时长字段的规则化建议
- 将 duration 离散为 duration_bucket，减少规则复杂度。
- 例如：当需求是“小于5秒”时，展开为 1s、2s、3s、4s 四条等值规则。
- 定价与匹配引擎均按 bucket 等值匹配，而不是区间比较。

## 入库建议
- 可将 _kie_param_scope_recommendation.csv 作为字段治理配置表初始化数据。
- 建议新增字段：scope(level), allow_override_to, reason, updated_at。
- 运行时按 scope 决定参数来源与可覆盖范围，并写入参数决策日志。
