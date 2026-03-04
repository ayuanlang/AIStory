# Prompt Skills (Claude Skills Style)

This directory organizes prompt assets into skill packages so the Agent can load prompts by `skill_id` instead of hard-coded file names.

## Structure

- `skills_registry.json`: global registry of skills and related prompt files.
- `<skill_id>/SKILL.md`: skill metadata and usage notes.
- `<skill_id>/system_prompt.txt`: primary system prompt for that skill (when applicable).

## Current Policy

- Existing legacy `.txt` prompts in `app/core/prompts/*.txt` remain valid.
- Agent orchestration prompt is migrated to `skills/agent_orchestrator/system_prompt.txt`.
- New runtime loader (`skills_loader.py`) resolves prompt text by skill id.

## How Agent Uses It

`LLMService.analyze_intent` loads `agent_orchestrator/system_prompt.txt` first. If unavailable, it falls back to in-code default prompt.
