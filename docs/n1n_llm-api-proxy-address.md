# API 接口调用地址

## 接口调用主地址与端点路径

### 一、国外访问推荐

| 类型 | 地址 | 特点 |
|------|------|------|
| 主站 | `https://api.n1n.ai` | 美国集群，国内访问一般 |
| CDN 分站 | `https://api.n1n.ai` | 全球 100+ 节点，国内访问特别快 |
| CF 站 | `https://api.n1n.ai` | 全球 CDN，国内访问一般 |

### 二、国内访问推荐

| 类型 | 地址 | 特点 |
|------|------|------|
| 主站 | `https://api.n1n.ai` | 美国集群，国内访问一般 |
| CDN 分站 | `https://api.n1n.ai` | 全球 100+ 节点，国内访问特别快 |
| CF 站 | `https://api.n1n.ai` | 全球 CDN，国内访问一般 |
| 亚洲加速镜像 | `https://hk.n1n.ai` | 香港服务器 |


### 三、端点路径地址

- **全球用户：一般情况下直接使用主地址**

```
https://api.n1n.ai
```
如果软件在主地址后无自动补全端点路径功能，则使用**完整地址（主地址 + 端点路径）**
```
https://api.n1n.ai/v1
https://api.n1n.ai/v1/chat/completions
https://api.n1n.ai/v1/responses
```

:::caution[注意]
如果你不确定使用哪个地址，建议依次尝试以上所有地址
:::



- **亚洲用户：可以使用亚洲区镜像加速，一般情况下直接使用镜像主地址**

:::tip[正常运行]
亚洲区镜像加速节点已恢复上线，以下地址为正确的香港节点地址
:::

```
https://hk.n1n.ai
```
同上，如主地址后无自动补全端点路径功能，则使用**完整地址（主地址 + 端点路径）**
```
https://hk.n1n.ai/v1
https://hk.n1n.ai/v1/chat/completions
https://hk.n1n.ai/v1/responses
```


:::tip[提示]
不同的厂商模型可能存在调用格式不同，以及不同的第三方软件/客户端要求不一样，具体的接口 URL 配置请详细查阅[接口配置教程](https://docs.n1n.ai/llm-api-quickstart)
:::


