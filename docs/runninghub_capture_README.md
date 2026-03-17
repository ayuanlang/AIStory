# RunningHub Capture Steps

## Goal

Prepare browser-rendered RunningHub docs so the local extractor can build a real snapshot and a deprecated-by-default import bundle.

## What To Save

You need two kinds of files:

1. Index file
   - Save the rendered content of `https://www.runninghub.cn/runninghub-api-doc-cn/llms.txt`
   - Recommended path: `docs/runninghub_capture/llms.txt`

2. Detail page files
   - Save the rendered content of each RunningHub model page you want to import.
   - Recommended folder: `docs/runninghub_capture/pages/`
   - Recommended filename: use the `api-xxxxxx` id from the URL.
   - Example:
     - `https://www.runninghub.cn/runninghub-api-doc-cn/api-425766743.md`
     - save as `docs/runninghub_capture/pages/api-425766743.md`

## Easiest Browser Method

For both the index page and each detail page:

1. Open the page in Edge or Chrome.
2. Wait until the page body is fully rendered.
3. Select the visible document text.
4. Copy it.
5. Paste into a local text file.

For detail pages, make sure the pasted file includes the `OpenAPI Specification` content and the YAML code block.

If the copied text does not include the opening and closing code fences, add them manually so the file contains:

```yaml
openapi: 3.0.1
...
```

## Minimum Useful Set

Start with a small set such as:

- `api-425766743.md` for image text-to-image
- `api-425766759.md` for image image-to-image
- `api-425766712.md` for video text-to-video
- `api-425766678.md` for video image-to-video
- `api-425766728.md` for voice text-to-audio

## Commands To Run After Files Are Ready

Step 1: build snapshot

`c:/storyboard/AIStory/.venv/Scripts/python.exe backend/_extract_runninghub_standard_openapi.py --index-file docs/runninghub_capture/llms.txt --page-cache-dir docs/runninghub_capture/pages --out docs/runninghub_openapi_snapshot.json`

Step 2: build field catalog, enum catalog, and deprecated import bundle

`c:/storyboard/AIStory/.venv/Scripts/python.exe backend/_build_runninghub_import_bundle.py --snapshot docs/runninghub_openapi_snapshot.json --field-csv docs/runninghub_field_catalog.csv --enum-csv docs/runninghub_enum_catalog.csv --import-json docs/runninghub_system_api_import_bundle.json`

## Important Constraint

All generated RunningHub import items are currently created as deprecated by default:

- `deprecated = true`
- `config.deprecated = true`
- `config.is_deprecated = true`
- `config.disable_api = true`

So this capture/import flow is safe for research and staging before runtime enablement.