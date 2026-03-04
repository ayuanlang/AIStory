# Skill: agent_orchestrator

## Purpose
Interpret user intent and produce a safe, executable tool plan for storyboard AIGC workflows.

## Inputs
- user query
- recent chat history
- project context
- auth context

## Outputs
JSON object:
- `reply`: concise natural language response
- `plan`: tool call list

## Tooling Notes
- Prefer read-first, then write actions.
- Respect permission constraints from backend policy checks.
- Use `search_project_data` before destructive updates when context is incomplete.
- Use `internet_search` only when project context is insufficient.
