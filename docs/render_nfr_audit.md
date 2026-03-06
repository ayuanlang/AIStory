# Render 非功能审计（安全 / 性能 / 存储）

日期：2026-02-26

## 审计范围
- 部署编排：`render.yaml`
- 后端运行时：FastAPI (`backend/app/main.py`, `backend/app/core/config.py`)
- 前端构建发布：Vite 静态站点（Render Static Service）

## 已落地改进

### 1) 安全（Security）
- 新增通用安全响应头中间件：
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  - HTTPS 下启用 `Strict-Transport-Security`
- `SECRET_KEY` 改为环境变量优先；Render 中配置 `generateValue: true`。
- Token 时效调整为可配置环境变量（默认 30 天，较原来 1 年更安全）。

### 2) 性能（Performance）
- 后端新增 GZip 中间件（可配置阈值，默认 1KB）。
- Render 后端服务加入 `healthCheckPath: /healthz`。
- 后端增加 `/healthz` 健康检查端点。
- Uvicorn 启动参数增加：`--proxy-headers --forwarded-allow-ips='*' --workers ${WEB_CONCURRENCY:-1}`。
- 前端构建改为 `npm ci --no-audit --no-fund`，提升可重复性与构建稳定性。

### 3) 存储（Storage）
- 现有持久盘挂载 `/backend/uploads` 保持不变（Render Disk，1GB）。
- 上传目录保持启动时自动创建，避免冷启动路径缺失。

## 风险与建议（未自动改动）

### 安全
- 建议增加认证接口限流（如登录/重置密码）以降低撞库与爆破风险。
- 建议对上传做 MIME + 内容签名校验（不仅依赖扩展名）。
- 建议补充 CSP（Content-Security-Policy），当前为兼容前端现状未强制开启。

### 性能
- 当前 `WEB_CONCURRENCY=1` 适配免费/低配实例；升级套餐后可按 CPU 调整到 2~4。
- 建议对图片/视频访问增加 CDN 或对象存储（R2/S3），降低应用容器 I/O 压力。

### 存储
- 1GB 持久盘对多项目视频场景很快触顶，建议：
  1. 增加生命周期清理策略（按创建时间/引用关系）
  2. 迁移冷数据到对象存储
  3. 在后台增加容量告警阈值（例如 80%）

## 验证记录
- 前端已执行 `npm run build` 成功。
- 改动文件已通过编辑器错误检查（无语法错误）。

## 追加审计：KIE 模型枚举一致性（2026-03-06）

### 背景
- 对 KIE Market 模型名进行“严格枚举对齐”复核，重点覆盖 Kling / Bytedance / Hailuo / Wan / Veo 相关文档页。
- 目标：确保系统内置配置、DB 种子数据、运行时别名映射与官方文档保持一致，并对文档歧义保留可追溯裁决记录。

### 本次落地
- 已完成高置信差异修正：
  - `kling/2.6-text-to-video` → `kling-2.6/text-to-video`
  - `kling/2.6-image-to-video` → `kling-2.6/image-to-video`
  - `kling/v25-turbo-text-to-video-pro` → `kling/v2-5-turbo-text-to-video-pro`
  - `kling/2.6-motion-control` → `kling-2.6/motion-control`
  - `kling/v25-turbo-image-to-video-pro` → `kling/v2-5-turbo-image-to-video-pro`
- 已同步运行时兼容别名，确保历史值仍可被解析，不破坏存量数据。
- 已补充别名文档与“歧义裁决依据”：`docs/kie_model_alias_map.md`。

### 取证与裁决原则
- 证据来源：`https://docs.kie.ai/sitemap.xml` + 目标模型中英文页面交叉核对。
- 裁决规则：
  1. 优先采用页面内 `model` 的 Value/Default/Example（若内部一致）；
  2. 若英文页内部冲突，交叉中文对应页；
  3. 仍冲突时，按页面路径语义与同族页面一致性裁决；
  4. 对被替换旧值必须保留 alias 做向后兼容。

### 变更时间线
- 2026-03-06（第一阶段）：完成批量枚举抓取、对照与首批高置信修正（Kling 2.6 T2V/I2V、Kling v2.5 Turbo T2V）。
- 2026-03-06（第二阶段）：完成歧义项二次核验并修正（Kling 2.6 Motion Control、Kling v2.5 Turbo I2V）；补充审计依据文档。

### 验证
- 受影响后端文件已完成错误检查（无新增语法/诊断错误）。
