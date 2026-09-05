# SKILL: shot_generation

## Name
Shot Generation (分镜生成)

## Purpose
将上游 Beats 结果转换为可执行的 AI 视频分镜提示词，输出标准 Shot 表格（`Shot Logic` + `Video Content (CN)`）。

## Prompt Source
- 主提示词文件：`skills/shot_generation.md`（分镜成稿）
- 视频提示词后优化（AgentScope，可选）：`skills/shot_video_prompt_optimize_agentscope.md`
- 执行器：`app.services.shot_generation_agentscope.generate_shots_content`
- 注册入口：`skills/skills_registry.json` 中 `id = shot_generation`

## Runtime
1. 主生成：`shot_generation.md` + 单次 LLM
2. 后优化：AgentScope 仅抛光 `Video Content (CN)`（不改拆镜/Logic）
3. 开关：`SHOT_VIDEO_PROMPT_OPTIMIZE_AGENT=on|off`（默认 on；失败保留草稿）

## Notes
- 不要把 Agent 流程写进 `shot_generation.md`；优化契约在独立提示词文件中。
- 每个 Pn 必须标本镜内起止秒：`(P1 0s–4s)`；P1 从 0s 起，相邻 P 首尾相接，末 P 止秒 = 本镜 Duration。
- 合镜完成后必须评估上下镜衔接（§三.3B）：转镜运镜与转镜其他要求拆成转出/转入，分别写入上镜末 P 与下镜 P1。
- 进出场不得压成一句（§二.3B）：须落地视线三拍（预看/跟看/对视）+ 在场者反应 + 已锁景别×配套运镜；缺反应标缺口、禁自造、禁首帧人已站定。
