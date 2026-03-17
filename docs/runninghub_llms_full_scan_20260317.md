# RunningHub llms.txt Full Scan 2026-03-17

Source: https://www.runninghub.cn/runninghub-api-doc-cn/llms.txt

This document is an index-level scan of RunningHub standard model APIs derived from llms.txt. It is intentionally limited to what can be stably extracted from the index page itself. Detail-page request schemas are not included here because many detail pages still degrade to an Apifox client-rendered shell when fetched outside the browser.

## Scan Result

- Standard model API entries stably identified from llms.txt: 149
- Video generation and processing: 93
- Image generation and processing: 36
- Audio generation and processing: 8
- 3D generation and processing: 12

## Video

- image-to-video by breadcrumb: 51
- reference-to-video by breadcrumb: 3
- text-to-video by breadcrumb: 29
- video-edit: 4
- motion-control: 5
- video-tools: 1

### Video Notes

- RunningHub exposes both provider-native families and platform-branded reseller families in the same catalog.
- Official stable tier is usually explicit in titles containing `官方稳定版`.
- Low-cost unstable tier is usually explicit in titles containing `低价渠道版`.
- Many provider-native models do not carry an explicit tier suffix in the title and should be treated as `unknown` until detail-page schema extraction is available.

### Major Visible Families

- Vidu
- 可灵 / Kling
- 万相 2.6
- Seedance
- 海螺 / Hailuo
- 全能视频 S
- 全能视频 X
- 全能视频 V3.1
- 悠船
- 即梦

## Image

- reference-to-image by breadcrumb: 1
- text-to-image by breadcrumb: 20
- image-to-image by breadcrumb: 15

### Major Visible Families

- 悠船文生图
- 全能图片 PRO
- 全能图片 V2
- 全能图片 G
- 全能图片 V1
- 全能图片 X
- Seedream
- 千问 2.0 / 2.0 Pro

## Audio

- text-to-audio: 8

### Major Visible Families

- minimax/speech-2.6-hd
- minimax/speech-2.6-turbo
- minimax/speech-2.8-hd
- minimax/speech-2.8-turbo
- minimax/speech-02-hd
- minimax/speech-02-turbo
- minimax/voice-clone
- minimax/music-2.5

## 3D

- text-to-3D: 1
- image-to-3D: 11

### Major Visible Families

- 混元文生 3D 模型 v3.1
- 混元图生 3D 模型 v3.1
- hitem3d v1.5
- hitem3d v2
- hitem3d portrait v1.5
- hitem3d portrait v2.0
- hitem3d portrait v2.1

## Classification Drift Found In llms.txt

These entries should not be imported purely by breadcrumb without a correction layer.

- `api-425766679` title is `全能视频S-文生视频-pro-官方稳定版`, but it appears under the `image-to-video` breadcrumb.
- `api-425766736` title is `Vidu-参考生视频-q2-pro`, but it appears under `图像生成与处理 > reference-to-image`; operationally it looks video-oriented.
- `api-425766748` title is `全能图片G-1.5-图生图-官方稳定版`, but it appears under the `text-to-image` breadcrumb.
- `api-427096745` and `api-427096746` appear under `image-to-video > kling`, but their slugs and titles indicate `reference-to-video`.

## Import Guidance

- Safe default: ingest these entries as index-only candidates.
- Mark all imported RunningHub items as deprecated and inactive until detail-page request schemas are captured from a rendered browser session.
- Add a normalization layer that prioritizes title and slug hints over breadcrumb text when the two disagree.

## Recommended Next Step

- Use this scan as the canonical inventory boundary.
- Then capture rendered detail pages only for the subsets you actually want to onboard first, such as `官方稳定版` video models or a single modality family.