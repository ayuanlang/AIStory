# 分组详细表格


# API 分组类型对比指南

## 分组类型及特点

:::highlight purple 💡
最新更新以具体页面的显示为准
:::

| 分组 | 类型 | 费率 | 支持模型 |
| :--- | :--- | :--- | :--- |
| default 默认 | 混合 ChatGPT（AZ渠道） + Claude（逆向渠道）+ MJ（快速模型）+ 国产模型（豆包 + DeepSeek + Qwen）| 官方费率 * 1 | OpenAI，Claude，国产模型 |
| 优质 Gemini | Gemini（Google 渠道）模型 | 官方费率 * 1 | Gemini |
| 官转 Gemini | Gemini（Google 渠道）模型，价格较贵（账号更多，成本更高）| 官方费率 * 3 | Gemini |
| 纯 AZ | 只有 ChatGPT 模型（AZ 渠道）+ 国产模型 | 官方费率 * 1.5 | OpenAI，Claude，国产模型 |
| 官转 | ChatGPT（AZ 渠道）+ ChatGPT（官转渠道）+ 国产模型（先用 AZ 渠道，不可用时使用官转渠道）| 官方费率 * 3 | OpenAI，国产模型 |
| 官转 OpenAI | ChatGPT 模型（官转渠道）| 官方费率 * 6 | OpenAI |
| 优质官转 OpenAI | ChatGPT 模型（官转渠道），价格较贵（账号更多）| 费率 * 8 | OpenAI |
| 逆向 | 支持 GPT + Claude + Gemini + Grok | 官方费率 * 1.4 | OpenAI，Claude |
| 限时特价 | 支持国产模型（豆包 + DeepSeek + Qwen）| 官方费率 * 0.6 | Gemini，国产模型 |
| 官转克劳德2 | Claude（AWS 官转渠道）| 官方费率 * 6 | Claude |
| 官转克劳德3 | Claude（AWS 官转渠道 + Anthropic 官转渠道）| 官方费率 * 12 | Claude |
| 直连克劳德 | Claude（Anthropic 官转渠道）| 官方费率 * 16 | Claude |
| Claude Code 专属 | Claude code | 官方费率 * 1.5 | Claude Code | 1 | 官方费率 * 1.5 | 官方费率 * 3 |
| Claude |  官方费率 * 1.4 | 官方费率 * 1 | 官方费率 * 1.5 | 官方费率 * 3 |
| Gemini |  官方费率 * 1.4 | 官方费率 * 1 | 官方费率 * 1.5 | 官方付费版（支持高并发） |
| MJ 绘画 | 无 | $0.24 一次 | 无 | 无 |

## 优缺点比较

 | 特点 | 逆向 | 默认（混合）| AZ | 官转 | 官转/优质官转 OpenAI | 优质 Gemini | 官转 Gemini | 官转克劳德 | 直连克劳德 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **优点** | ChatGPT 官网同款，更聪明，价格优惠，但是回复和 API 有些不一样，虽然都是一个模型，但是估计官方给的版本不同 | ChatGPT 官网同款，更聪明，价格优惠 | 通道多，备用足，量大、高并发，无审核，支持 FC、TC | 高速、量大、高并发，无审核，支持 FC、TC | ChatGPT 官网同款，高速、量大、高并发，账号更多，更稳定 | 官网同款，更聪明，价格优惠，量大，稳定 | 官网同款，更聪明，价格优惠，量大，更稳定，账号更多 | 来自 AWS 和 Anthropic 官方，通道多，备用足，量大、高并发 | 来自 Anthropic 官方，账号更多，更稳定 |
| **缺点** | 非官方接口 | 非官方接口 | 有时 Azure 会卡顿 | 受官方 API 稳定性影响 | 受官方 API 稳定性影响 | 受官方 API 稳定性影响 | 成本更高，倍率更高，受官方 API 稳定性影响 | 受官方 API 稳定性影响 | 受官方 API 稳定性影响 |
| **介绍** | 均采用 OpenAI 官方逆向严禁频繁 sayl 等健康测试 | 逆向、az 混合、官转 | 采用企业无审核 Azure，支持 FC、TC 支持 1000w tpm，会用 OpenAI 做失败兜底 | 均采用 OpenAI 官方渠道，支持 FC、TC，支持 1000w tpm3.5 使用 OpenAI 大额账号，并发高 | 采用 OpenAI 官方渠道，支持 FC、TC，支持 1000w tpm3.5 使用 OpenAI 大额账号，并发高 | 谷歌官方 API，大额账号，并发高 | 谷歌官方 API，大额账号，并发高 | 均采用官方渠道，支持函数调用、Claude Code，大额账号，并发高 | 均采用官方渠道，支持函数调用、Claude Code，大额账号，并发高 |

## 模型支持情况

| 模型类型 | 逆向 | 默认（混合） | Azure | 官转 |
|----------|------|--------------|---------------------|--------------|
| GPT-4 | 逆向，全部支持 | 逆向，全部支持 | Azure，全部支持 | OpenAI，全部支持 |
| GPT-3.5 | 逆向，全部支持 | 逆向，全部支持 | Azure，全部支持 | OpenAI，全部支持 |
| OpenAI 其他基础模型 | 全部支持 | 全部支持 | 全部支持 | 全部支持 |
| Midjourney | 不支持 | 全部支持 | 不支持 | 不支持 |
| 国产模型 | 不支持 | 全部支持 | 部分支持 | 不支持 |
| Claude | 逆向，全部支持 | 全部支持 | 全部支持 |逆向，全部支持 |

## 注意事项

- **ChatGPT 官转渠道**：来自 openai.com
- **AZ 渠道**：来自微软 Azure
- **Gemini Google 渠道**：来自谷歌
- **国产模型**：来自各自官方
- **Claude AWS 官转**：来自亚马逊
- **Claude Anthropic 官转**：来自 Anthropic 官方

> 可在[令牌](https://n1n.ai/console/token)页面添加令牌，并给令牌添加相应的分组，从而只调用该分组下的模型。
