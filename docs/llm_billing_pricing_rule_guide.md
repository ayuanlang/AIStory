---
title: AIStory 计费流程与定价规则配置指南（供 LLM 使用）
version: 1.3
last_updated: 2026-03-08
scope: 后端计费与定价规则配置
source_of_truth:
  - backend/app/services/billing_service.py
  - backend/app/api/settings.py
  - backend/app/api/endpoints.py
  - backend/app/models/all_models.py
  - backend/app/schemas/settings.py
llm_mode: strict-json-first
---

# 1. 文档目标

本文档用于沉淀 AIStory 计费与定价规则的实现级设计，面向后续 LLM Agent 自动化配置场景。

LLM 需要具备以下能力：
1. 理解完整计费生命周期（预扣、结算、取消、回退）。
2. 通过系统接口安全配置定价。
3. 为文本、图片、视频生成一致且可执行的规则负载。
4. 避免使用已废弃的旧定价接口。

# 2. 核心原则

1. 定价更新仅允许针对已存在的 `SystemAPISetting`（更新优先，不自动新建）。
2. 对用量不确定场景采用“先预扣、后结算”。
3. 细粒度规则多条命中时，按“计算成本最高”优先。
4. 结算阶段若细粒度规则无命中且开启 granular，回退到预扣金额。
5. 全链路审计：`transaction_history` + `transaction_action` 双表留痕。
6. 定价规则单表事实源：`system_api_billing_rules` 为唯一运行时定价来源。

# 3. 计费相关数据模型

## 3.1 `system_api_settings`

计费关联与开关字段：
- `billing_unit_type`: `per_call | per_second | per_minute | per_token | per_1k_tokens | per_million_tokens`
- `billing_cost`: 基础成本
- `billing_cost_input`: 输入 token 成本
- `billing_cost_output`: 输出 token 成本
- `has_granular_billing_rules`: 是否启用细粒度规则

说明：`system_api_settings` 不再承载定价列；运行时定价仅来自 `system_api_billing_rules`。

辅助字段：
- `category`、`provider`、`model`、`modality`、`tags`、`config`

## 3.2 `system_api_billing_rules`

按 `system_api_id` 绑定的定价规则表（运行时单一事实源）。

支持：
- 模式开关：`applies_to_text`、`applies_to_image`、`applies_to_video`
- 匹配维度：
  - 文本：token 区间
  - 图片：张数、宽高、像素
  - 视频：时长、fps、是否有声
  - 通用：`generation_mode`、`input_format`、`output_format`
- 定价字段：
  - `billing_unit_type`、`billing_cost`、`billing_cost_input`、`billing_cost_output`
- 优先级字段：
  - `priority`、`is_active`

## 3.3 `transaction_history`

账务流水主表：
- 负数金额：扣费/预扣
- 正数金额：退款/充值
- `details` 内携带计费分解与结算引用

## 3.4 `transaction_action`

生命周期动作审计表：
- `stage`: `RESERVED | SETTLED | CANCELED | REFUND | CHARGE`
- 记录预扣成本、实际成本、delta、命中规则、用量元数据等

# 4. 全链路走查

## 4.1 预检查阶段

1. 确认 `task_type`：`llm_chat | analysis | analysis_character | image_gen | video_gen | ...`
2. 根据 `task_type` 映射类别。
3. 加载用户余额并判断计费路径。

路径分支：
- 用量不确定：调用 `reserve_credits(...)`
- 固定成本：`check_balance(...)` 后直接 `deduct_credits(...)`

## 4.2 预扣阶段

`reserve_credits(db, user_id, task_type, provider, model, details)`：
1. 调用 `estimate_cost_breakdown(..., phase="reserve")`
2. 从用户余额扣除预估金额
3. 写入 `transaction_history`（负金额，details 标记 RESERVED）
4. 写入 `transaction_action`（stage=RESERVED）

## 4.3 结算阶段

`settle_reservation(db, reservation_tx_id, actual_details)`：
1. 规范化实际用量字段（`input_tokens` / `output_tokens` / `total_tokens`）
2. 调用 `estimate_cost_breakdown(..., phase="settle", reserved_cost_fallback=reserved_cost)`
3. 计算 `delta = actual_cost - reserved_cost`：
   - `delta < 0`：退款
   - `delta = 0`：无补充流水
   - `delta > 0`：补扣；余额不足时记录 outstanding
4. 更新预扣流水为 SETTLED
5. 写入 `transaction_action`（stage=SETTLED）

## 4.4 取消阶段

`cancel_reservation(db, reservation_tx_id, error_msg)`：
1. 全额退回预扣
2. 写入退款流水
3. 更新预扣流水状态为 CANCELED
4. 写入 `transaction_action`（stage=CANCELED）

# 5. 成本计算逻辑

## 5.1 总成本

`total_cost = feature_cost + api_cost`

其中：
- `feature_cost` 来自 `System_Payment/feature_pricing/global`
- `api_cost` 来自 `system_api_billing_rules` 命中的规则

## 5.2 单位类型行为

- `per_call`：固定值
- `per_second`：`cost * duration_seconds`
- `per_minute`：`cost * duration_seconds / 60`
- token 计费：
  - `((input_tokens * cost_input) + (output_tokens * cost_output)) / divisor`
  - `divisor = 1 | 1000 | 1000000`
  - 若 `cost_input/cost_output` 为 0 且 `cost > 0`，则用总 token 按基础成本计算

## 5.3 细粒度规则选择

当 `has_granular_billing_rules=true`：
1. 过滤所有 active 规则并执行条件匹配。
2. 对每条命中规则计算成本。
3. 按以下顺序排序：
   - 计算成本降序
   - priority 降序
   - id 降序
4. 取第一条作为最终规则。

若结算时无规则命中且存在预扣回退值：
- 使用预扣金额作为 api_cost（安全回退）

# 6. 配置接口契约

## 6.1 细粒度规则管理

- `GET /settings/system/manage/{system_api_id}/billing-rules`
- `POST /settings/system/manage/{system_api_id}/billing-rules`
- `POST /settings/system/manage/billing-rules/{rule_id}`
- `DELETE /settings/system/manage/billing-rules/{rule_id}`

行为说明：
- 新增/更新/删除规则后，会刷新 `has_granular_billing_rules`。

## 6.2 功能定价与默认 API 定价

- `GET /billing/feature-pricing`
- `PUT /billing/feature-pricing`
- `GET /billing/default-api-pricing`
- `PUT /billing/default-api-pricing`

## 6.3 旧接口禁用说明

以下旧接口已从代码中移除，不可再使用：
- `/billing/rules`
- `/billing/rules/sync`
- `/billing/rules/{rule_id}`

# 7. LLM 配置协议

## 7.1 LLM 必须遵循的决策流程

每次定价任务必须执行：
1. 先按 `provider + category + model` 定位现有 `SystemAPISetting`。
2. 若不存在，更新模式下禁止自动新建。
3. 先产出预览方案。
4. 写入前必须请求用户明确确认。
5. 写入后返回字段级变更摘要。

## 7.2 LLM 输出契约（严格 JSON）

```json
{
  "intent": "update_pricing",
  "targets": [
    {
      "provider": "string",
      "category": "LLM|Image|Video|Voice|Music|Vision|Tools",
      "model": "string",
      "exists_required": true,
      "base_pricing": {
        "billing_unit_type": "per_call|per_second|per_minute|per_token|per_1k_tokens|per_million_tokens",
        "billing_cost": 0,
        "billing_cost_input": 0,
        "billing_cost_output": 0
      },
      "granular_mode": {
        "enabled": false,
        "rules": []
      }
    }
  ],
  "requires_confirmation": true,
  "confirmation_text": "请确认执行以上更新"
}
```

## 7.3 细粒度规则负载模板

```json
{
  "system_api_id": 123,
  "name": "视频1080p有声t2v规则",
  "description": "1080p文生视频且有声",
  "is_active": true,
  "priority": 100,
  "applies_to_text": false,
  "applies_to_image": false,
  "applies_to_video": true,
  "generation_mode": "t2v",
  "input_format": "text",
  "output_format": "video",
  "has_audio": true,
  "duration_seconds_min": 4,
  "duration_seconds_max": 10,
  "fps_min": 24,
  "fps_max": 30,
  "width_min": 1920,
  "height_min": 1080,
  "billing_unit_type": "per_second",
  "billing_cost": 120,
  "billing_cost_input": 0,
  "billing_cost_output": 0,
  "extra_conditions": {}
}
```

# 8. 规则设计建议（给 LLM）

1. 尽量避免区间重叠，降低歧义。
2. 必须重叠时，用更高 `priority` 明确胜出规则。
3. LLM token 计费场景应同时设置 `billing_cost_input` 与 `billing_cost_output`。
4. 图片/视频固定单价场景，token 成本字段保持 `0`。
5. 规则启用前应使用代表性 usage 元数据做验证。
6. 即便启用 granular，也应保留合理的基础定价作为兜底。
7. 当规则依赖关键元数据时，可在 `extra_conditions.required_keys` 中声明必须出现的 usage 字段。

## 8.1 不同元数据字段个数的匹配策略

系统支持规则只声明部分字段：
1. 规则中未声明的字段视为通配，不参与匹配。
2. 规则中声明的字段全部满足时，规则才会进入候选集。
3. 若 `extra_conditions.required_keys` 存在，则请求 usage 必须带齐这些字段（并且值有效），否则该规则不命中。

候选规则排序优先级：
1. `priority`（高优先）
2. `specificity_score`（规则声明维度越具体越高）
3. `computed_cost`（规则计算成本）
4. `id`（稳定排序兜底）

`required_keys` 示例：

```json
{
  "extra_conditions": {
    "required_keys": ["duration_seconds", "width", "height"],
    "require_success_output": true
  }
}
```

上例表示：即使其他条件满足，只要缺少 `duration_seconds/width/height` 中任一字段，该规则仍不命中。

# 9. 配置后校验清单

1. 规则表中的成本字段均为非负整数。
2. `billing_unit_type` 在允许枚举内。
3. `has_granular_billing_rules` 与 active 规则存在性一致。
4. 预扣用例通过：
   - 预扣流水创建成功
   - 用户余额按预期减少
5. 结算三路径通过：
   - 命中规则退款路径
   - 命中规则补扣路径
   - 无命中回退到预扣金额
6. 取消路径可全额退回。
7. `transaction_action` 审计字段完整。

# 10. 推荐执行模式

## 模式A：仅分析

只输出候选变更方案并请求确认，不执行写入。

## 模式B：确认后执行

在用户明确确认后，写入基础定价与可选细粒度规则。

## 模式C：回归验证

按场景矩阵执行验证并返回可审计证据。

# 11. 场景矩阵（建议）

1. 文本 token 计费：低 token 用量命中低成本规则。
2. 文本 token 计费：高 token 用量命中高成本规则。
3. 图片 per_call 分辨率分层：512 与 2K。
4. 视频 per_second 有声分层：无声与有声。
5. 多规则重叠命中：验证最高计算成本胜出。
6. granular 开启但无命中：结算回退到 `reserved_cost`。

# 12. LLM 强约束

1. 禁止调用废弃接口 `/billing/rules*`。
2. 禁止跳过写入确认。
3. 更新模式下禁止自动新建缺失目标。
4. `strict-json-first` 要求下禁止输出不可解析文本。
5. 成本字段禁止负值。

# 13. 最小可复用中文提示词

```text
你是 AIStory 定价配置助手。
规则：
1) 只更新已存在的 system_api_settings
2) 所有写入前必须用户确认
3) 以 system_api_billing_rules 为定价事实源
4) granular 规则重叠时按“最高计算成本优先”
5) 输出严格 JSON（按第7.2节结构）
```

# 14. 中文提示词模板（可直接复制给 LLM）

以下模板默认用于“系统管理 Agent / 定价管理 Agent”。

## 14.1 模板A：仅分析，不写入

```text
你是 AIStory 的计费与定价规则分析助手。

目标：
1. 只分析，不执行任何写入。
2. 基于现有 system_api_settings 评估定价是否合理。
3. 输出可执行的“候选更新方案”。

强约束：
1. 不允许调用或建议使用废弃接口 /billing/rules*。
2. 不允许新增 system_api_settings（仅 update existing）。
3. 输出必须是严格 JSON，不要输出解释性散文。
4. 定价必须是非负整数。
5. 如涉及 granular 规则，明确说明命中条件、优先级、预期成本。

输出 JSON 结构：
{
  "intent": "analyze_pricing",
  "targets": [
    {
      "provider": "...",
      "category": "LLM|Image|Video|Voice|Music|Vision|Tools",
      "model": "...",
      "exists_required": true,
      "current_pricing": {
        "billing_unit_type": "...",
        "billing_cost": 0,
        "billing_cost_input": 0,
        "billing_cost_output": 0
      },
      "suggested_pricing": {
        "billing_unit_type": "...",
        "billing_cost": 0,
        "billing_cost_input": 0,
        "billing_cost_output": 0
      },
      "granular_mode": {
        "enabled": false,
        "rules": []
      },
      "reason": "..."
    }
  ],
  "requires_confirmation": true,
  "confirmation_text": "请确认执行以上更新"
}
```

## 14.2 模板B：已确认后执行写入

```text
你是 AIStory 的计费配置执行助手。

当前状态：用户已明确确认“执行更新”。

执行目标：
1. 仅更新已存在的 system_api_settings 行。
2. 按确认内容更新规则表中的基础规则（base_pricing）：
   - billing_unit_type
   - billing_cost
   - billing_cost_input
   - billing_cost_output
3. 如提供 granular 规则，则调用 billing-rules CRUD 接口写入。
4. 写入后返回变更摘要和校验结果。

强约束：
1. 严禁新建 system_api_settings。
2. 严禁使用废弃接口 /billing/rules*。
3. 如目标不存在，标记 failed 并给出缺失清单。
4. 输出严格 JSON。

输出 JSON 结构：
{
  "intent": "apply_pricing",
  "applied": [
    {
      "provider": "...",
      "category": "...",
      "model": "...",
      "updated_fields": [
        "billing_unit_type",
        "billing_cost",
        "billing_cost_input",
        "billing_cost_output"
      ],
      "granular_rules": {
        "created": [1, 2],
        "updated": [3],
        "deleted": []
      },
      "status": "completed"
    }
  ],
  "failed": [
    {
      "provider": "...",
      "category": "...",
      "model": "...",
      "reason": "target_not_found"
    }
  ],
  "post_check": {
    "all_cost_non_negative": true,
    "unit_type_valid": true,
    "has_granular_flag_consistent": true
  }
}
```

## 14.3 模板C：回归验证（走查结果输出）

```text
你是 AIStory 的计费回归验证助手。

请对以下场景执行走查验证，并输出严格 JSON：
1. reserve 成功（扣减预扣金额）
2. settle 退款路径（actual < reserved）
3. settle 补扣路径（actual > reserved）
4. granular 多规则命中时“最高成本规则”胜出
5. granular 无命中时 settle 回退到 reserved_cost
6. cancel_reservation 全额退回

输出 JSON 结构：
{
  "intent": "verify_billing",
  "scenarios": [
    {
      "name": "reserve_success",
      "status": "pass|fail",
      "evidence": {
        "reservation_tx_id": 0,
        "transaction_action_stage": "RESERVED"
      }
    },
    {
      "name": "settle_refund",
      "status": "pass|fail",
      "evidence": {
        "reservation_tx_id": 0,
        "settlement_tx_id": 0,
        "delta": -10
      }
    }
  ],
  "summary": {
    "pass_count": 0,
    "fail_count": 0,
    "risk_notes": []
  }
}
```

## 14.4 模板D：系统提示词（推荐放在 Agent System Prompt）

```text
你是 AIStory 定价与计费配置助手。

你必须遵守：
1. 仅更新已有 system_api_settings，不可在定价更新流程中创建新模型。
2. 所有写入前必须要求用户显式确认。
3. 只能使用当前有效接口：
   - /settings/system/manage/{system_api_id}/billing-rules
   - /billing/feature-pricing
   - /billing/default-api-pricing
4. 禁止使用废弃接口：/billing/rules、/billing/rules/sync、/billing/rules/{id}
5. 输出优先使用严格 JSON，字段必须可机器解析。
6. 若规则重叠，按“最高计算成本优先”原则设计 priority 和区间。
7. 任何成本字段不得为负数。
```

# 15. KIE 各类 API 计费规则（2026-03-08 快照）

本节基于 `https://kie.ai/zh-CN/pricing`，并参考 KIE 各模型详情页与文档目录（`https://docs.kie.ai/llms.txt`）整理。用于快速落地一版可运行的 KIE 计费规则。

重要说明：
1. KIE 官方价格会动态调整，本节是快照，不是永久常量。
2. 规则落地时建议以 USD/CNY 金额为基准，不直接按供应商积分点数换算（避免供应商积分体系差异）。
3. 当前系统成本字段为整数；遇到 KIE 小数积分（例如 5.5/次）需执行统一取整策略。

## 15.1 数据来源

1. 定价主源：`https://kie.ai/zh-CN/pricing`
2. 模型详情（用于补充计费维度/参数）：
   - `https://kie.ai/gpt-5-2`
   - `https://kie.ai/kling-3-0`
   - `https://kie.ai/kling-2-6`
   - `https://kie.ai/sora-2`
   - `https://kie.ai/seedream5-0-lite`
   - `https://kie.ai/nano-banana-2`
   - `https://kie.ai/elevenlabs/text-to-dialogue-v3`
   - `https://kie.ai/suno-api?model=ai-music-api%2Fboost-music-style`
   - `https://kie.ai/recraft-remove-background`
3. 文档索引源：`https://docs.kie.ai/llms.txt`

## 15.2 建议的统一换算与取整策略

固定换算常量（当前业务规则）：
1. `1 KIE 积分 = 3 系统积分`
2. `1 USD = 7 CNY`
3. `1 系统积分 = 0.01 CNY`（即 `1 CNY = 100 系统积分`）

1. 金额口径优先：
   - 先取 KIE 页面给出的 USD 价格（或先换算到 CNY）。
   - 再按系统口径换算为 credits（例如：`1 分人民币 = 1 系统积分`）。
2. 若仅有 KIE credits 且无稳定金额时，先写入临时规则并标记 `source=kie_credit_snapshot`，待金额校准后替换。
3. 小数成本统一采用 `ceil`（向上取整）防止低估成本。
4. 规则元数据必须落 `supplier_info`，至少包含：`source_url`、`snapshot_date`、`raw_price_text`。

## 15.3 分类规则建议（可直接配置）

### A. Chat/LLM（单位：`per_million_tokens`）

| 模型 | 输入成本 | 输出成本 | 备注 |
|---|---:|---:|---|
| `gpt-5-2` | 87.5 / M tokens | 700 / M tokens | 定价页原文含 Input/Output 双价 |
| `gemini-3-flash` | 30 / M tokens | 180 / M tokens | 适合低成本高吞吐 |
| `gemini-3-pro` | 100 / M tokens | 700 / M tokens | 高质量高成本档 |

落地建议：
1. `billing_unit_type=per_million_tokens`
2. `billing_cost_input`、`billing_cost_output` 分别填写
3. `billing_cost` 可置 0（避免和 input/output 双重计费）

### B. Image（单位：`per_call`）

| 模型/档位 | 成本 | 备注 |
|---|---:|---|
| `google/nanobanana2` 1K | 8 / image | 定价页 |
| `google/nanobanana2` 2K | 12 / image | 定价页 |
| `google/nanobanana2` 4K | 18 / image | 定价页 |
| `seedream/5-lite-text-to-image` | 5.5 / image | 需按策略取整 |
| `seedream/5-lite-image-to-image` | 5.5 / image | 需按策略取整 |
| `recraft/remove-background` | 1 / image | 定价页与模型页一致 |

落地建议：
1. `billing_unit_type=per_call`
2. 按分辨率拆 granular 规则：
   - 1K/2K/4K 可用 `width/height/pixels` 区间
3. `seedream 5.5` 采用 `ceil => 6`（或统一乘倍率再回填整数）

### C. Video（单位优先：`per_second`，部分模型用 `per_call`）

| 模型/档位 | 成本 | 建议单位 |
|---|---:|---|
| `kling-3.0` 720P 无音频 | 20 / s | `per_second` |
| `kling-3.0` 720P 有音频 | 30 / s | `per_second` |
| `kling-3.0` 1080P 无音频 | 27 / s | `per_second` |
| `kling-3.0` 1080P 有音频 | 40 / s | `per_second` |
| `kling-2.6` 5s 无音频 | 55 / video | `per_call` |
| `kling-2.6` 10s 无音频 | 110 / video | `per_call` |
| `kling-2.6` 10s 有音频 | 220 / video | `per_call` |
| `sora-2` 稳定 10s | 35 / video | `per_call` |
| `sora-2` 稳定 15s | 40 / video | `per_call` |

落地建议：
1. Kling 3.0 用 `per_second`，并用 granular 维度区分：`has_audio` + 分辨率。
2. Kling 2.6 / Sora 2 优先用 `per_call`，并按 `n_frames`、`duration_seconds` 建分档规则。
3. 对 `text-to-video` / `image-to-video` 分开 `generation_mode`，避免混价。

### D. Music / Voice（当前引擎兼容策略）

| 模型/能力 | 官方计费维度 | 快照价格 |
|---|---|---:|
| `elevenlabs/text-to-dialogue-v3` | per 1000 characters | 14 / 1k chars |
| `ai-music-api/boost-music-style` | per request | 0.4 / request |

兼容建议：
1. `boost-music-style` 可直接映射 `per_call`（小数按 `ceil` 可取 1）。
2. `elevenlabs` 字符计费建议新增单位 `per_1k_chars`（最佳实践）。
3. 若短期不扩展单位，先以 `per_call` 临时落地，并在 `extra_conditions` 标记 `char_based=true`，后续替换为字符真计费。

## 15.4 可执行规则模板（示例）

### 示例1：Kling 3.0（1080P 有声）

```json
{
  "name": "kling3-1080p-audio",
  "is_active": true,
  "priority": 300,
  "applies_to_video": true,
  "applies_to_text": false,
  "applies_to_image": false,
  "generation_mode": "t2v",
  "has_audio": true,
  "width_min": 1920,
  "height_min": 1080,
  "billing_unit_type": "per_second",
  "billing_cost": 40,
  "billing_cost_input": 0,
  "billing_cost_output": 0,
  "extra_conditions": {
    "source": "https://kie.ai/zh-CN/pricing",
    "snapshot_date": "2026-03-08"
  }
}
```

### 示例2：Nano Banana 2（分辨率分层）

```json
[
  {
    "name": "nanobanana2-1k",
    "priority": 100,
    "applies_to_image": true,
    "billing_unit_type": "per_call",
    "billing_cost": 8,
    "pixels_max": 1310720
  },
  {
    "name": "nanobanana2-2k",
    "priority": 110,
    "applies_to_image": true,
    "billing_unit_type": "per_call",
    "billing_cost": 12,
    "pixels_min": 1310721,
    "pixels_max": 4194304
  },
  {
    "name": "nanobanana2-4k",
    "priority": 120,
    "applies_to_image": true,
    "billing_unit_type": "per_call",
    "billing_cost": 18,
    "pixels_min": 4194305
  }
]
```

### 示例3：GPT-5.2（输入输出拆分）

```json
{
  "name": "gpt-5-2-base",
  "is_active": true,
  "priority": 100,
  "applies_to_text": true,
  "billing_unit_type": "per_million_tokens",
  "billing_cost": 0,
  "billing_cost_input": 88,
  "billing_cost_output": 700,
  "extra_conditions": {
    "rounding": "input_from_87.5_to_88",
    "source": "https://kie.ai/zh-CN/pricing",
    "snapshot_date": "2026-03-08"
  }
}
```

## 15.5 上线前检查项（KIE 专项）

1. 至少抽样 1 个 Chat、1 个 Image、1 个 Video 模型做端到端计费回放。
2. 检查 `transaction_history.details` 是否记录 `supplier_pricing_snapshot` 与 `pricing_scheme_snapshot`。
3. 对小数成本模型确认取整策略一致（避免分析与落库不一致）。
4. 对 `per_call` 视频模型确认时长档位条件命中正确。
5. 建议每周自动比对一次 `kie.ai/zh-CN/pricing`，触发价格漂移告警。

## 15.6 建议的维护机制

1. 建立 `kie_pricing_snapshot`（JSON）版本库：按日期存储原始快照。
2. 维护 `pricing_source_hash`，检测官网变更后触发人工复核。
3. 将“建议规则”与“已生效规则”分离：
   - 建议规则：由 AI 助手生成
   - 生效规则：由管理员确认后写入

