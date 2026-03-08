# 非计费改动待办清单

最后更新：2026-03-08
用途：跟踪核心计费走查范围之外的改动，后续分批处理。

## 1. 高优先级（运行稳定性）

- [ ] `backend/app/main.py`：验证维护模式与安全头中间件改造，重点关注 SSE 场景。
- [ ] `backend/app/core/logging.py`：验证请求体回放逻辑，避免流式响应忙循环或断连监听异常。
- [ ] `backend/app/db/session.py`：验证 SQLite WAL 在本地与部署环境的并发行为。
- [ ] `backend/app/services/llm_service.py`：验证流式解析与 JSON 回退解析稳定性。
- [ ] `backend/app/services/agent_service.py`：验证流式链路、计划解析、确认门控与 LLM 回退逻辑。
- [ ] `frontend/src/components/AgentChat.jsx`：验证流式 UI、性能与会话历史持久化。
- [ ] `frontend/src/components/GlobalAIAssistant.jsx`：验证桌面与移动端拖拽/缩放体验。
- [ ] `frontend/src/services/api.js`：验证 SSE 客户端稳健性与 `async_mode=1` 兼容性。

## 2. 中优先级（数据与模式一致性）

- [ ] `backend/app/models/all_models.py`：审查新增/扩展字段与迁移兼容性。
- [ ] `backend/app/db/init_db.py`：验证初始化迁移幂等性与旧库回填安全性。
- [ ] `backend/app/services/media_service.py`：验证 provider key pool 接入与 modality 匹配。
- [ ] `backend/app/services/modality_utils.py`：验证模态映射完整性与向后兼容。
- [ ] `backend/migrate_system_api_modality_v2.py`：先在备份库演练再用于生产。
- [ ] `backend/backfill_kie_modality.py`：确认模型覆盖范围与避免误覆盖。
- [ ] `backend/app/data/system_api_seed.json`：执行 seed 导入导出一致性检查。
- [ ] `backend/export_system_api_seed.py`：确认敏感字段剥离与输出稳定性。

## 3. 中优先级（管理端与交互）

- [ ] `frontend/src/pages/UserAdmin.jsx`：验证 provider key pool 的 CRUD 流程与表单校验。
- [ ] `frontend/src/pages/Settings.jsx`：确认密码/API key 输入框 autocomplete 行为。
- [ ] `frontend/src/index.css`：评估 markdown 样式对全局 UI 的影响。

## 4. 低优先级（临时文件清理）

- [ ] `_test_endpoint.py`：确认保留或删除。
- [ ] `_test_ep.py`：确认保留或删除。
- [ ] `_test_out.txt`：若不再使用则删除。
- [ ] `_test_result.txt`：若不再使用则删除。
- [ ] `backend/aistory.db-shm`：从版本管理中移除并补充 ignore 规则。
- [ ] `backend/aistory.db-wal`：从版本管理中移除并补充 ignore 规则。

## 5. 相关但可延后

- [ ] `backend/add_system_api_granular_billing_tables.py`：纳入统一迁移体系（Alembic 或统一迁移执行器）。
- [ ] `backend/app/services/pricing_tools.py`：评估外部源稳定性与超时/降级策略。

## 6. 建议执行顺序

1. 运行稳定性（第1节）
2. 数据与模式一致性（第2节）
3. 管理端与交互（第3节）
4. 临时文件清理（第4节）
5. 延后项（第5节）
