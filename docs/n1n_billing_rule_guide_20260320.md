# n1n Billing Rule Guide 2026-03-20

## Billing Formula

- Primary rule: `actual_price = upstream_official_price x selected_group_multiplier`
- n1n docs explicitly describe pricing by group multiplier rather than a unified model price table.
- The selected token group is part of the billing identity and can change the price of the same upstream model.

## Captured Group Multipliers

- default 默认: 官方费率 * 1 | supports=OpenAI，Claude，国产模型
- 优质 Gemini: 官方费率 * 1 | supports=Gemini
- 官转 Gemini: 官方费率 * 3 | supports=Gemini
- 纯 AZ: 官方费率 * 1.5 | supports=OpenAI，Claude，国产模型
- 官转: 官方费率 * 3 | supports=OpenAI，国产模型
- 官转 OpenAI: 官方费率 * 6 | supports=OpenAI
- 优质官转 OpenAI: 费率 * 8 | supports=OpenAI
- 逆向: 官方费率 * 1.4 | supports=OpenAI，Claude
- 限时特价: 官方费率 * 0.6 | supports=Gemini，国产模型
- 官转克劳德2: 官方费率 * 6 | supports=Claude
- 官转克劳德3: 官方费率 * 12 | supports=Claude
- 直连克劳德: 官方费率 * 16 | supports=Claude
- Claude Code 专属: 官方费率 * 1.5 | supports=Claude Code
- MJ 绘画: $0.24 一次 | supports=无

## Fixed-Price Exceptions

- MJ 绘画: $0.24 per call

## Internal Mapping Guidance

- LLM / Chat / Responses / Embeddings: default to `per_million_tokens` once upstream official token prices are sourced.
- Image families: default to `per_call` once the upstream official image price is sourced.
- Video families: keep unresolved until upstream billing basis is confirmed; many upstream providers are `per_second`, but this is not uniformly documented by n1n.
- Voice / Music families: keep unresolved or temporary `per_call` staging until official upstream billing units are captured.

## Import Guardrail

- Do not apply zero-cost placeholder billing rows to production settings.
- Generate direct pricing rules only after a model-level official price baseline is available for the exact group/provider pairing.
- If you need an interim admin view, store the multiplier logic in `supplier_info` only and keep billing inactive.