# RunningHub Standard API Integration

## Goal

Build a reusable supplier-ingestion pattern for RunningHub that can automatically extract:

- standard model API catalog
- request field dictionary
- enum candidates and value domains
- standard-dimension mapping candidates
- async runtime contract metadata

The output should be usable by both `system_api_settings` and the data-dictionary / enum-mapping workflow that already exists for KIE.

## What RunningHub Exposes

RunningHub has a clear two-layer structure:

1. Discovery layer
   - `https://www.runninghub.cn/runninghub-api-doc-cn/llms.txt`
   - Acts as the provider index.
   - Contains category breadcrumbs, model/API page links, task-query links, upload links, webhook links, and schema links.

2. Detail layer
  - Each standard model page renders a fenced OpenAPI YAML block in the browser.
  - Important: raw HTTP fetches to the `.md` page currently return an Apifox SPA shell, not the rendered markdown body.
  - Deterministic extraction therefore needs either browser-rendered fetch or a stable Apifox content endpoint.
  - After rendered content is obtained, the YAML block carries the request path, method, root request properties, required fields, enums, and the async response shape.

## Provider Traits That Should Be Standardized

RunningHub standard model APIs are not raw vendor APIs. They are a provider-normalized async task protocol with model-specific request bodies.

Shared traits:

- Auth: `Authorization: Bearer <API_KEY>`
- Submit: each SKU has its own POST endpoint under `/openapi/v2/...`
- Result model: async task response with `taskId`, `status`, `results`, `usage`, `failedReason`
- Status values: `QUEUED`, `RUNNING`, `SUCCESS`, `FAILED`
- Resource upload: `/openapi/v2/media/upload/binary`
- Webhook: optional callback via `webhookUrl` on workflow / app APIs, plus webhook debug endpoints

This means RunningHub should be modeled as:

- provider = `runninghub`
- provider protocol = `async_task_submit_then_query`
- model page = per-SKU schema source
- query/upload/webhook pages = shared runtime protocol source

## Recommended Pipeline

### 1. Index Discovery

Source: `llms.txt`

Extract from each standard-model line:

- breadcrumb path
- title
- doc URL
- short summary
- modality category
- generation mode candidates
- service tier

RunningHub-specific service tier normalization:

- `官方稳定版` -> `official_stable`
- `低价渠道版` -> `low_cost_channel`
- otherwise -> `unknown`

### 2. Page Extraction

For each selected standard-model page:

- fetch page markdown
- extract fenced OpenAPI YAML
- parse:
  - endpoint path
  - HTTP method
  - request root properties
  - required fields
  - field types
  - enum values
  - defaults
  - output response contract
  - `x-sku-id` if present

Current extraction constraint:

- `requests.get(page_url)` is not enough for detail parsing because RunningHub detail pages are client-rendered.
- The extractor must explicitly mark `detail_parse_status = client_rendered_shell` rather than silently returning empty endpoint metadata.

### 3. Field Dictionary Generation

Generate one field-catalog row per request field.

Recommended output columns:

- provider
- api_title
- doc_url
- endpoint
- method
- category
- generation_modes
- service_tier
- source_field
- source_type
- required
- enum_values
- default_value
- format
- description
- example

This is the RunningHub equivalent of the KIE field-dimension inventory, but it should keep non-enum fields too.

### 4. Standard Mapping Candidate Generation

Map source fields to shared system dimensions when confidence is high.

Recommended direct mappings:

| RunningHub field | Standard dimension |
| --- | --- |
| `prompt` | `TEXT_INPUT` |
| `aspectRatio` | `ASPECT_RATIO` |
| `resolution` | `RESOLUTION_TIER` |
| `size` | `FRAME_SIZE` |
| `image_size` | `IMAGE_SIZE_CLASS` |
| `duration` | `DURATION_SECONDS` |
| `mode` | `MODE` |
| `quality` | `QUALITY_LEVEL` |
| `output_format` | `OUTPUT_FORMAT` |
| `imageUrl` | `REFERENCE_IMAGE_URL` |
| `imageUrls` | `REFERENCE_IMAGE_URLS` |
| `text` | `TEXT_INPUT` |
| `sound` | `SOUND_SUPPORTED` |
| `multi_shots` | `MULTI_SHOTS_SUPPORTED` |
| `voice_id` | `VOICE_ID` |
| `emotion` | `EMOTION` |
| `enable_base64_output` | `RETURN_BASE64` |
| `english_normalization` | `ENGLISH_NORMALIZATION` |

Recommended provider-level derived dimensions:

| Derived dimension | Rule |
| --- | --- |
| `GENERATION_MODE` | infer from breadcrumb and endpoint path |
| `SERVICE_TIER` | infer from title / summary |
| `HAS_AUDIO` | infer from summary and output description |
| `REFERENCE_IMAGE_LIMIT` | infer from array limits or summary text |
| `ASYNC_PROTOCOL` | fixed = `task_submit_query` |
| `UPLOAD_REQUIRED` | true if request references provider-hosted media URLs or file upload pre-step |

### 5. System API Seed Preparation

The extracted model page should be convertible into `system_api_settings` seed data with:

- `provider = runninghub`
- `api_url = model endpoint`
- `category`
- `model` or `base_model` from title / endpoint slug
- `generation_modes`
- `supplier_info.source_urls`
- `supplier_info.runninghub.sku_id`
- `supplier_info.runninghub.service_tier`
- `supplier_info.runninghub.async_contract`
- `config.enum_catalog`
- wide columns synchronized from extracted capabilities

Import target:

- Generate an import bundle in the existing `SystemAPISettingImportRequest` shape.
- Feed that bundle into the existing `/settings/system/manage/import` path.
- New RunningHub rows must be generated with `deprecated = true`, `config.deprecated = true`, `config.is_deprecated = true`, and `config.disable_api = true` by default.
- Only after runtime adapter validation should individual rows be un-deprecated.

### 6. Runtime Contract Normalization

The runtime layer should not treat every RunningHub model page as a unique provider shape. It should normalize once:

- submit response:
  - `taskId`
  - `status`
  - `errorCode`
  - `errorMessage`
  - `results[]`
  - `usage`

- query/status endpoints:
  - `/task/openapi/status`
  - `/task/openapi/outputs` and V2 successor

- upload endpoint:
  - `/openapi/v2/media/upload/binary`
  - use `download_url` for standard model API input URLs
  - use `fileName` for workflow-node references

This should become one provider adapter, not dozens of one-off adapters.

## RunningHub vs KIE

KIE pipeline today is roughly:

1. crawl vendor docs
2. extract field/value matrix
3. generate enum catalog
4. map into standard dimensions
5. seed DB
6. reverse-map at runtime

RunningHub should reuse the same shape, with one key difference:

- KIE source pages are less uniform and rely more on heuristics.
- RunningHub standard model pages are much more uniform after render because they publish OpenAPI YAML.

So RunningHub should prefer deterministic extraction first, then use LLM enrichment only for:

- capability hints hidden in prose
- billing clues hidden in summary text
- ambiguous field semantics

## Suggested Intermediate Artifacts

Recommended generated files:

- `runninghub_standard_api_index.json`
  - list of standard model pages discovered from `llms.txt`
- `runninghub_openapi_snapshot.json`
  - parsed endpoint + request/response field structures
- `runninghub_field_catalog.csv`
  - flat field dictionary for data-dictionary import
- `runninghub_enum_catalog.csv`
  - enum-only rows for mapping workflow
- `runninghub_standard_mapping_candidates.csv`
  - source field / source enum -> standard dimension / standard value

## Priority Field Families

The following field families appear early and should be normalized first:

1. Image generation
   - `prompt`
   - `resolution`
   - `aspectRatio`
   - `imageUrls`

2. Video generation
   - `prompt`
   - `duration`
   - `size`
   - `imageUrl`
   - reference-image lists for reference-to-video

3. Audio generation
   - `text`
   - `voice_id`
   - `speed`
   - `volume`
   - `pitch`
   - `emotion`
   - `enable_base64_output`

## Concrete Findings From Current RunningHub Docs

Validated against current pages:

- Image text-to-image pages expose fields such as `resolution`, `prompt`, `aspectRatio`.
- Image image-to-image pages expose `imageUrls`, `prompt`, `resolution`, optional `aspectRatio`.
- Video text-to-video pages expose `prompt`, `size`, `duration`.
- Video image-to-video pages expose `prompt`, `duration`, `imageUrl`.
- Audio text-to-audio pages expose `text`, `pronunciation_dict`, `voice_id`, `speed`, `volume`, `pitch`, `emotion`, `enable_base64_output`, `english_normalization`.
- Standard-model submit responses already embed the async task contract; no separate vendor-specific response parser is required per model.

## Implementation Direction

The right implementation pattern in this repo is:

1. Reuse the KIE-style `llms.txt` deterministic pre-parser pattern.
2. Add a RunningHub-specific extractor that outputs structured JSON and flat field rows.
3. Keep DB writes in a separate loader step.
4. Reuse existing standard-dimension and runtime reverse-mapping infrastructure where field families overlap.

## Next Practical Step

Use `backend/_extract_runninghub_standard_openapi.py` to generate the first deterministic snapshot. If direct HTTP fetch returns the Apifox shell, pass a browser-captured index via `--index-file` and rendered detail pages via `--page-cache-dir`.

Then run `backend/_build_runninghub_import_bundle.py` to emit:

- field catalog CSV
- enum catalog CSV
- deprecated-by-default system API import bundle

Then decide whether to:

- build a CSV/SQL loader like KIE, or
- feed the snapshot into the existing supplier-feature-analysis flow for LLM enrichment.