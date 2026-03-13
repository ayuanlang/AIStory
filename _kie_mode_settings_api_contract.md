# 全 Provider 参数枚举映射契约（联调版）

## 目标
- 对所有 provider 的生成请求参数进行“按数据字典反推 + 允许枚举约束”。
- 覆盖 image/video/voice 路径，不只 KIE。
- 对非法枚举值自动回退，避免向上游 API 提交无效参数。

## 运行时决策优先级
1. 请求显式参数（如 mode/aspect_ratio/image_size/duration）
2. 项目级覆盖参数（如有）
3. Settings 中 provider+model 配置（system_api_settings + config）
4. provider/model 默认参数

## 推荐字段定义

### 1) Settings 读接口返回（示例）
```json
{
  "provider": "grsai",
  "defaults": {
    "output_format": "png",
    "mode": "standard"
  },
  "model_param_defaults": {
    "veo3-fast": {
      "mode": "standard",
      "aspect_ratio": "16:9",
      "duration": 5
    }
  },
  "enum_catalog": {
    "mode": ["standard", "pro"],
    "aspect_ratio": ["16:9", "9:16"],
    "image_size": ["1K", "2K"],
    "resolution": ["720p", "1080p"],
    "durations_seconds": [5, 10]
  },
  "scope": {
    "mode": "settings",
    "mode_allow_override_to": ["project"]
  }
}
```

### 2) Settings 写接口请求（示例）
```json
{
  "provider": "vidu",
  "model_param_defaults": {
    "vidu2.0": {
      "aspect_ratio": "16:9",
      "duration": 4
    }
  }
}
```

### 3) 项目设置写接口请求
```json
{
  "project_id": 1001,
  "provider": "kie",
  "overrides": {
    "mode": "std"
  }
}
```

### 4) 生成接口请求（可选显式覆盖）
```json
{
  "prompt": "A cyberpunk city skyline",
  "provider": "wanxiang",
  "model": "wanx2.1-i2v-plus",
  "aspect_ratio": "9:16",
  "duration": 5,
  "mode": "turbo",
  "resolution": "2k"
}
```

## 运行时解析输出（建议写日志）
```json
{
  "resolved_params": {
    "mode": "standard",
    "aspect_ratio": "9:16",
    "resolution": "1080p",
    "duration": 5
  },
  "resolution_trace": {
    "mode": {
      "source": "request",
      "candidates": ["turbo", "standard"],
      "fallback_applied": true,
      "reason": "not_in_allowed_enum"
    }
  },
  "status": "resolved"
}
```

## 回退规则
1. 枚举类字段（mode/aspect_ratio/image_size/resolution）
- 若请求值不在 allowed 枚举中，回退到该字段 allowed 首项或 provider 默认值。

2. 时长字段（duration）
- 若不在 durations_seconds 中，回退到 durations_seconds 首项。
- 若超过 max_duration，裁剪到 max_duration。

3. 能力开关字段（sound/multi_shots）
- 若 system_api_settings 标记 unsupported，则强制关闭，避免上游拒绝。

## 错误返回建议
```json
{
  "error": "enum_value_not_supported",
  "message": "Requested value is not supported by provider/model enum constraints.",
  "field": "mode",
  "requested": "turbo",
  "supported": ["standard", "pro"],
  "suggested": "standard"
}
```

## 对现有代码接入点
1. 解析与下发
- backend/app/services/media_service.py
  - _execute_generation_by_provider
  - _apply_runtime_enum_constraints
  - _handle_kie_generation（保留 provider 特定二次守卫）

2. settings 能力与规则管理
- backend/app/api/settings.py

3. 计费维度继承 mode
- backend/app/services/billing_service.py
  - _extract_usage_metadata
  - _rule_matches_usage

## 前端最小联调建议
1. Settings 页面新增 mode 选择器（单选下拉）
2. 项目设置页新增 mode 覆盖开关
3. 生成页保留高级参数 mode（可选）
4. 若不填，后端按优先级自动决策
