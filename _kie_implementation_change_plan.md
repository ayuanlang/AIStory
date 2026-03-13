# KIE 参数标准化 + 枚举匹配 + 定价重构实施清单

## 目标
- 建立统一参数标准层（用户主控参数 -> 供应商参数）。
- 在调用 API 前完成枚举合法性匹配与回退。
- 使用离散化后的计费维度命中定价规则。
- 全链路可追溯：每次请求保留参数决策日志与命中规则。

## 阶段 0：数据库准备（已可执行）
### 变更文件
- _kie_param_mapping_schema.sql
- _kie_param_mapping_seed.sql
- _build_kie_param_mapping_seed_sql.py

### 执行步骤
1. 执行 schema SQL，创建参数映射相关表。
2. 维护 CSV 模板后重新生成 seed SQL。
3. 执行 seed SQL。

### 验收标准
- 能查询到 profile 和 rules。
- 可按 model_key + ratio + quality 返回 target_field/target_value 组合。

---

## 阶段 1：请求参数标准化（调用前）
### 目标
- 前端/上游只需传主参数（ratio, quality）。
- 后端自动补齐 aspect_ratio/resolution/size/image_resolution/image_size。
- mode 在 Settings 中按 model 绑定可配置（provider+model -> default_mode），并在调用时自动注入请求参数（允许项目级覆盖）。

### 变更文件与函数
1. backend/app/api/endpoints.py
- VideoGenerationRequest: 增加可选字段 ratio, quality（保留现有字段兼容）。
- GenerationRequest: 增加可选字段 ratio, quality（图像入口统一主控参数）。
- 在视频提交流程中，调用参数解析器并写入 reserve_details。

2. backend/app/services/media_service.py
- 新增函数 resolve_kie_param_payload(model_key, ratio, quality, raw_payload, db_session)
  - 输入：model_key, ratio, quality, 已有 payload_input。
  - 输出：resolved_payload, fallback_events, status。
- 在 _handle_kie_generation 中调用上述解析器，再进入现有 model-specific payload 逻辑。
- 在 _execute_generation_by_provider 中将解析后的字段注入 active_config 或 provider_options，避免分支重复改写。
- mode 读取优先级：请求显式 mode > 项目设置 mode > Settings(model 绑定) mode > 模型默认。

### 验收标准
- 用户只给 9:16 + 2k 时，P1/P2/P3/P4/P5 不同画像均能输出合法 payload。
- 不支持时返回结构化冲突信息，而不是沉默修改。

---

## 阶段 2：系统设置与能力数据对齐
### 目标
- 让现有 system_api_settings 的能力字段和新映射规则协同。
- 让 Settings API 显式暴露 model 绑定 mode 默认值并可被项目设置覆盖。

### 变更文件与函数
1. backend/app/models/all_models.py
- 保持现有 SystemAPISetting 与 SystemAPIBillingRule 不变。
- 可新增映射引擎模型类（若你希望通过 ORM 管理新表）：
  - KieModelCapabilityProfile
  - KieModelProfileBinding
  - KieParamAutoMappingRule
  - KieParamResolutionLog

2. backend/app/db/init_db.py
- 在现有 Ensure system_api_billing_rules table exists 附近增加新表 ensure。
- 迁移逻辑保持幂等（checkfirst + 兼容 SQLite/Postgres）。

3. backend/app/api/settings.py
- 增加 profile 绑定管理接口（model_key -> profile_code）。
- 增加 mapping rules 批量导入接口（可直接接 CSV/JSON）。
- 增加/确认 mode 设置项读写接口（用户级 provider+model 绑定默认），并在系统设置输出中附带 mode 可选值。

### 验收标准
- 管理端可维护 profile、rules、model 绑定。
- 修改后可即时影响参数解析结果。

---

## 阶段 3：计费维度离散化与规则命中
### 目标
- 用离散字段定价，降低区间匹配复杂度。

### 变更文件与函数
1. backend/app/services/billing_service.py
- 在 _extract_usage_metadata 中新增派生字段：
  - ratio_bucket
  - quality_bucket
  - duration_bucket
  - n_frames_bucket
- 在 _rule_matches_usage 中增加 extra_conditions 离散字段匹配。
- 保留现有区间匹配，作为过渡兼容路径。

2. backend/app/api/settings.py
- 扩展 _replace_kie_granular_billing_rules：支持离散 bucket 规则写入 extra_conditions。
- 扩展 _build_kie_resolution_granular_rules_from_note：可选生成 quality_bucket 规则。

### 时长离散化策略（强制）
- 当策略是小于 5 秒时，展开为 1、2、3、4 四条规则。
- 每条规则通过 duration_bucket 等值命中，不走区间比较。

### 验收标准
- 同一请求在预估与结算命中同一规则 ID。
- 能通过 duration_bucket 精确区分 1-4 秒规则。

---

## 阶段 4：可观测性与回放
### 目标
- 任何一次参数回退或定价命中都可追踪。

### 变更文件与函数
1. backend/app/services/media_service.py
- 在参数解析完成后写 kie_param_resolution_logs。

2. backend/app/services/billing_service.py
- 在结算结果中附带 matched_rule_id 和关键 usage 维度快照。

3. backend/app/api/settings.py
- 增加调试查询接口：
  - 查询某 model_key 在 ratio+quality 下的解析结果。
  - 查询某请求的参数解析日志与计费命中详情。

### 验收标准
- 给定 transaction_id 可回放完整链路：输入参数 -> 映射 -> API payload -> 命中规则 -> 扣费。

---

## 任务拆分建议（可直接排期）
### Sprint A（2-3 天）
1. 接入 schema + seed + model binding。
2. 在 media_service 完成 resolve_kie_param_payload 并接到 KIE 调用。
3. 打通最小日志。

### Sprint B（2-3 天）
1. 计费服务新增 bucket 派生与匹配。
2. 设置服务支持离散规则导入。
3. 做并行对账（新旧规则同时跑）。

### Sprint C（1-2 天）
1. 上线切换开关。
2. 冲突提示与管理端调试查询完善。

---

## 回归测试清单
1. 参数映射
- 输入 9:16 + 2k，不同 profile 输出字段不同但都合法。
- square-only 模型返回冲突提示。

2. 计费
- 同 model 同 ratio 不同 quality 命中不同规则。
- duration 1/2/3/4 分别命中不同 bucket 规则。

3. 兼容性
- 老请求只传 aspect_ratio/resolution 仍可成功。
- 旧 system_api_billing_rules 在未配置新 bucket 规则时保持可用。

---

## 风险与应对
1. 规则过多导致维护成本上升
- 通过 profile 继承和默认规则减少重复。

2. 文档枚举变更导致规则过期
- 定期从枚举目录重建规则并做差异审计。

3. 新旧逻辑切换风险
- 加 feature flag，先灰度项目级开启。
