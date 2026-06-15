# Script Progress Control Center Contract

## Purpose
Define the executable contract for a project-level progress and diagnostics center across script production.

This contract is the single source of truth for:
- Progress/state tracking by hierarchy (project -> pipeline -> script -> scene -> task).
- Issue reporting and escalation.
- Event-driven orchestration from scene import to storyboard generation.
- Parallel asset generation by asset type.

---

## 1) Hierarchy And Granularity

### L0 Project
- Scope: whole project.
- Goal: global health, end-to-end progress, blockers.

### L1 Pipeline
- Fixed stages:
  1. `script_optimization` (script-level)
  2. `asset_extraction` (script-level)
  3. `scene_planning` (scene-level, marker-driven)
  4. `storyboard_generation` (scene-level)
  5. `asset_generation` (scene x asset_type-level)

### L2 Script Work Unit
- Primary key: `script_id`.
- Used for: optimization and extraction progress.

### L3 Scene Work Unit
- Primary key: `scene_id`.
- Derived from scene markers in optimized script.

### L4 Task Work Unit
- Primary key: `task_id`.
- Includes storyboard and asset tasks.

---

## 2) Canonical Status Model

Allowed status values (`node_status`):
- `queued`
- `running`
- `success`
- `warning`
- `failed`
- `blocked`
- `skipped`

### Required Transition Rules
- `queued -> running -> success|warning|failed|blocked`
- `failed -> queued` (retry)
- `blocked -> queued` (dependency recovered)
- `running -> blocked` (runtime dependency loss)
- `skipped` is terminal unless manual re-open.

### SLA Diagnostics (default)
- `queued` > 10 min without pickup -> `warning`.
- `running` > 1.5 x node P95 duration -> `warning`.
- retry exhausted -> `failed` + issue severity `BLOCKER`.

---

## 3) Scene Marker Parsing Contract

Scene parsing MUST use the output markers:
- Block start: `[SCENES_BLOCK_START]`
- Block end: `[SCENES_BLOCK_END]`
- Scene start: `[SCENE_START:{scene_id}]`
- Scene end: `[SCENE_END:{scene_id}]`

### Validation Rules
1. Block markers must exist and be ordered.
2. Scene start/end markers must be paired by same `scene_id`.
3. Scene markers cannot overlap.
4. `scene_id` must be unique inside one `script_id`.

If any rule fails:
- Mark `scene_planning` node as `failed`.
- Emit issue code `SCENE_MARKER_PARSE_ERROR`.
- Do not trigger scene import for invalid units.

---

## 4) Event Bus Contract

All events MUST include common envelope:

```json
{
  "event_id": "evt_xxx",
  "event_type": "SceneImported",
  "event_version": "1.0",
  "project_id": "proj_xxx",
  "script_id": "scr_xxx",
  "scene_id": "EP01_SC01",
  "occurred_at": "2026-06-15T10:00:00Z",
  "producer": "scene_orchestrator",
  "payload": {}
}
```

### 4.1 SceneImported
Trigger: scene planner finishes one valid scene import.

`payload`:
```json
{
  "scene_text": "string",
  "scene_order": 1,
  "source_marker_range": {
    "start_token": "[SCENE_START:EP01_SC01]",
    "end_token": "[SCENE_END:EP01_SC01]"
  }
}
```

Consumer actions:
- Create storyboard job for this `scene_id`.
- Create asset-type jobs for this `scene_id` (see section 6).

### 4.2 StoryboardJobQueued
Trigger: storyboard job created.

`payload`:
```json
{
  "job_id": "job_sb_xxx",
  "priority": "normal",
  "retry_limit": 3
}
```

### 4.3 StoryboardReady
Trigger: storyboard generation success.

`payload`:
```json
{
  "job_id": "job_sb_xxx",
  "shot_count": 12,
  "duration_ms": 23000,
  "artifact_ref": "uri_or_db_ref"
}
```

### 4.4 AssetTypeQueued
Trigger: one asset type job created for a scene.

`payload`:
```json
{
  "job_id": "job_as_xxx",
  "asset_type": "character|prop|environment|poster",
  "priority": "normal",
  "retry_limit": 3
}
```

### 4.5 AssetTypeReady
Trigger: one asset type job succeeded.

`payload`:
```json
{
  "job_id": "job_as_xxx",
  "asset_type": "character",
  "asset_count": 5,
  "duration_ms": 18000,
  "artifact_ref": "uri_or_db_ref"
}
```

### 4.6 NodeFailed
Trigger: any node fails terminally.

`payload`:
```json
{
  "node_level": "script|scene|task",
  "node_name": "scene_planning",
  "error_code": "SCENE_MARKER_PARSE_ERROR",
  "error_message": "marker mismatch",
  "retry_count": 3,
  "retry_limit": 3,
  "is_blocker": true
}
```

---

## 5) Minimal Data Model (Storage Contract)

## 5.1 `project_progress_snapshots`
- `id` (pk)
- `project_id` (index)
- `overall_status` (`queued|running|success|warning|failed|blocked|skipped`)
- `health_score` (0-100)
- `progress_percent` (0-100)
- `blocked_count` (int)
- `failed_count` (int)
- `warning_count` (int)
- `created_at` (timestamp)

## 5.2 `pipeline_nodes`
- `id` (pk)
- `project_id` (index)
- `script_id` (nullable, index)
- `scene_id` (nullable, index)
- `node_name` (`script_optimization|asset_extraction|scene_planning|storyboard_generation|asset_generation`)
- `asset_type` (nullable: `character|prop|environment|poster`)
- `status` (`node_status`)
- `progress_percent` (0-100)
- `started_at` (nullable)
- `ended_at` (nullable)
- `duration_ms` (nullable)
- `retry_count` (default 0)
- `retry_limit` (default 3)
- `depends_on` (json array of node ids or logical refs)
- `last_error_code` (nullable)
- `last_error_message` (nullable)
- `updated_at` (timestamp)

## 5.3 `scene_units`
- `id` (pk)
- `project_id` (index)
- `script_id` (index)
- `scene_id` (index, unique per script)
- `scene_order` (int)
- `scene_text` (text)
- `marker_start_token` (string)
- `marker_end_token` (string)
- `import_status` (`queued|running|success|failed|blocked`)
- `parse_status` (`success|failed`)
- `parse_error_code` (nullable)
- `created_at` (timestamp)
- `updated_at` (timestamp)

## 5.4 `issues`
- `id` (pk)
- `project_id` (index)
- `script_id` (nullable, index)
- `scene_id` (nullable, index)
- `severity` (`INFO|WARNING|BLOCKER`)
- `status` (`open|acknowledged|resolved`)
- `issue_code` (index)
- `title` (string)
- `details` (text)
- `owner_domain` (`scene-parser|orchestrator|storyboard-engine|asset-queue|asset-worker|other`)
- `node_ref` (nullable)
- `first_seen_at` (timestamp)
- `last_seen_at` (timestamp)

## 5.5 `event_outbox`
- `id` (pk)
- `event_id` (unique)
- `event_type` (index)
- `event_version` (string)
- `project_id` (index)
- `script_id` (nullable, index)
- `scene_id` (nullable, index)
- `payload_json` (json)
- `publish_status` (`pending|published|failed`)
- `retry_count` (int)
- `created_at` (timestamp)
- `published_at` (nullable)

---

## 6) Orchestration Rules

### 6.1 Script-Level (must be script granularity)
1. Run `script_optimization(script_id)`.
2. On success, run `asset_extraction(script_id)`.
3. On success, run scene parsing/planning from optimized script markers.

### 6.2 Scene-Level (marker-driven)
For each valid `scene_id`:
1. Create `scene_unit`.
2. Import scene.
3. Emit `SceneImported`.
4. Queue storyboard job for same `scene_id`.

### 6.3 Asset Generation (asset_type granularity)
On `SceneImported`, enqueue independent jobs per asset type:
- `character`
- `prop`
- `environment`
- `poster`

Each job has isolated status and retry policy.
Panel MUST show progress at `scene_id + asset_type` resolution.

---

## 7) Read/Write API Contract

Base prefix (suggested): `/api/progress-center`

## 7.1 Query APIs

### GET `/api/progress-center/projects/{project_id}/overview`
Returns project-level summary.

Response:
```json
{
  "project_id": "proj_xxx",
  "overall_status": "running",
  "health_score": 82,
  "progress_percent": 61.5,
  "counts": {
    "scripts_total": 8,
    "scripts_done": 4,
    "scenes_total": 96,
    "scenes_done": 57,
    "tasks_running": 12,
    "issues_open": 9,
    "issues_blocker": 2
  }
}
```

### GET `/api/progress-center/projects/{project_id}/pipeline-nodes`
Query nodes by hierarchy filters.

Query params:
- `script_id` (optional)
- `scene_id` (optional)
- `node_name` (optional)
- `asset_type` (optional)
- `status` (optional, multiple)

### GET `/api/progress-center/projects/{project_id}/scenes`
Returns scene units and statuses.

### GET `/api/progress-center/projects/{project_id}/issues`
Query issue center.

Query params:
- `severity`
- `status`
- `owner_domain`
- `script_id`
- `scene_id`

## 7.2 Command APIs

### POST `/api/progress-center/scenes/import`
Input:
```json
{
  "project_id": "proj_xxx",
  "script_id": "scr_xxx",
  "scene_id": "EP01_SC01"
}
```
Behavior:
- Import scene.
- Emit `SceneImported` when successful.

### POST `/api/progress-center/storyboard/queue`
Input:
```json
{
  "project_id": "proj_xxx",
  "script_id": "scr_xxx",
  "scene_id": "EP01_SC01",
  "priority": "normal"
}
```

### POST `/api/progress-center/assets/queue-by-type`
Input:
```json
{
  "project_id": "proj_xxx",
  "script_id": "scr_xxx",
  "scene_id": "EP01_SC01",
  "asset_types": ["character", "prop", "environment", "poster"]
}
```

### POST `/api/progress-center/issues/{issue_id}/resolve`
Mark issue resolved with operator and note.

---

## 8) Panel Rendering Requirements

The diagnostics panel MUST support:
1. Hierarchical drill-down (L0 -> L4).
2. Node status heatmap by script and scene.
3. Scene marker parse diagnostics.
4. Scene import timeline and storyboard trigger timeline.
5. Asset progress matrix by `scene_id x asset_type`.
6. Unified issue center with blocker-first sorting.

---

## 9) Error Codes (Initial Set)

- `SCENE_MARKER_BLOCK_MISSING`
- `SCENE_MARKER_PAIR_MISMATCH`
- `SCENE_MARKER_DUPLICATE_SCENE_ID`
- `SCENE_IMPORT_FAILED`
- `STORYBOARD_JOB_FAILED`
- `ASSET_TYPE_JOB_FAILED`
- `DEPENDENCY_BLOCKED`
- `QUEUE_TIMEOUT`

---

## 10) Implementation Order (Recommended)

1. Add canonical status enum + transition guard.
2. Add scene marker parser + validation errors.
3. Add `scene_units` and `pipeline_nodes`.
4. Add outbox events + `SceneImported` trigger.
5. Add storyboard and asset-type queue consumers.
6. Add issue center persistence and escalation.
7. Add read APIs for panel.
8. Add panel hierarchy drill-down and matrix views.

