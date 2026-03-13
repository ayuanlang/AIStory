# KIE 参数映射引擎落地步骤

## 1. 建表
执行 _kie_param_mapping_schema.sql，创建四张表：
- kie_model_capability_profiles
- kie_model_profile_bindings
- kie_param_auto_mapping_rules
- kie_param_resolution_logs

## 2. 导入种子规则
1) 先维护 CSV 模板：
- _kie_model_capability_profiles_template.csv
- _kie_param_auto_mapping_rules_template.csv

2) 生成 SQL：
- python _build_kie_param_mapping_seed_sql.py

3) 执行输出：
- _kie_param_mapping_seed.sql

## 3. 绑定模型到画像
在 kie_model_profile_bindings 写入 model_key -> profile_code：
- model_key: bytedance/v1-pro-text-to-video -> profile_code: P1
- model_key: bytedance/seedream-v4-text-to-image -> profile_code: P2

## 4. 运行时决策（核心）
输入：model_key, ratio(如9:16), quality(如2k)
1) 查 profile_code。
2) 按 profile_code + ratio + quality 查规则。
3) 按 priority 生成 payload。
4) 执行 fallback_action（降档、默认值、冲突提示）。
5) 写入 kie_param_resolution_logs。

## 5. 与现有定价规则衔接
- 推荐将命中的 target_field/target_value 形成 billing_key。
- billing_key 示例：
  - model_key=bytedance/v1-pro-text-to-video
  - ratio=9:16
  - quality=2k
  - resolved_fields=aspect_ratio,resolution
- 将 billing_key 对接 system_api_billing_rules 的新重构字段，支持精确定价。

## 6. 你现在可以直接做的事
- 先只开两个前端控件：比例、清晰度。
- 后端按规则自动补全其余参数。
- 冲突时返回结构化提示（例如只支持 square）。
