
import requests
import json

# The base URL of your running backend service
BASE_URL = "http://127.0.0.1:8000"

# Data parsed from the user's request
N1N_MODELS_DATA = [
    {
        "name": "gpt-5.3-codex-medium",
        "category": "LLM",
        "description": "GPT-5.3-Codex-Medium 通过 性能碾压、功能泛化 和 安全升级，重新定义了AI在开发与生产力场景的角色.",
        "pricing": {"input": 1.4000, "output": 11.2000, "unit": "M_tokens"}
    },
    {
        "name": "gpt-5.3-codex-xhigh",
        "category": "LLM",
        "description": "GPT-5.3-Codex-XHigh 是一款专为编程、系统操作和多领域专业任务优化的高性能AI模型，具备顶尖代码能力、安全防御和实时交互功能，适合开发者和企业高效解决复杂问题。",
        "pricing": {"input": 1.4000, "output": 11.2000, "unit": "M_tokens"}
    },
    {
        "name": "gpt-5.2-codex",
        "category": "LLM",
        "description": "是一个能够理解极度复杂的系统架构、能够零错误编写整个软件项目、甚至能自我纠错的神级编程 AI",
        "pricing": {"input": 1.4000, "output": 11.2000, "unit": "M_tokens"}
    },
    {
        "name": "gpt-image-1.5-all",
        "category": "Image",
        "description": "gpt-image-1.5的逆向",
        "pricing": {"unit_price": 0.078, "unit": "image"}
    },
    {
        "name": "gpt-5.1-all",
        "category": "LLM",
        "description": "GPT-5.1：更智能、更具对话性的聊天GPT，最常用的型号，现在更温暖、更智能，更能遵循您的指令。",
        "pricing": {"input": 1.2500, "output": 10.0000, "unit": "M_tokens"}
    },
    {
        "name": "gpt-5.1-codex-max",
        "category": "LLM",
        "description": "GPT-5.1-codex-max 它突破了上下文理解与逻辑推理的极限，专为统筹跨仓库的系统级重构、自主设计并落地全栈生态、以及实现“零错误”的极端边缘场景而生。",
        "pricing": {"input": 0.7500, "output": 6.0000, "unit": "M_tokens"}
    },
    {
        "name": "gpt-5.1-thinking-all",
        "category": "LLM",
        "description": "GPT-5.1：更智能、更具对话性的聊天GPT，先进的推理模型，现在更容易理解，处理简单任务速度更快，处理复杂任务更持久。",
        "pricing": {"input": 1.2500, "output": 10.0000, "unit": "M_tokens"}
    },
    {
        "name": "gpt-5.2-all",
        "category": "LLM",
        "description": "gpt-5.2的逆向模型",
        "pricing": {"input": 1.7500, "output": 14.0000, "unit": "M_tokens"}
    },
    {
        "name": "sora-2-all",
        "category": "Video",
        "description": "sora-2的逆向，支持10s，15s，都是720p",
        "pricing": {"unit_price": 0.200, "unit": "video"}
    },
    {
        "name": "sora-2-pro-all",
        "category": "Video",
        "description": "sora-2-pro的逆向，支持15s和25s，15s支持1080p和720p，25s只支持720p",
        "pricing": {"unit_price": 3.600, "unit": "video"}
    },
    {
        "name": "sora-2-vip-all",
        "category": "Video",
        "description": "sora-2模型的逆向，暂时支持10s",
        "pricing": {"unit_price": 2.500, "unit": "video"}
    },
    {
        "name": "gpt-5.1-codex",
        "category": "LLM",
        "description": "GPT-5.1-codex 则是装备精良的“重装主力”。它专为解决最棘手的编程挑战、处理大规模代码库以及提供深度架构指导而设计，是企业级和高复杂度开发场景的首选模型。",
        "pricing": {"input": 0.7500, "output": 6.0000, "unit": "M_tokens"}
    },
    {
        "name": "sora-2-characters",
        "category": "Video",
        "description": "OpenAI 推出的 Sora Character 功能(也称为 Cameo 功能)，通过创建自定义角色并获取唯一的 Character ID,你可以让同一角色在无数视频中保持完美一致的外观和特征。",
        "pricing": {"unit_price": 0.010, "unit": "video"}
    },
    {
        "name": "gpt-4o-image-vip",
        "category": "Image",
        "description": "4o系列最新图片生成功能 VIP版本",
        "pricing": {"unit_price": 0.120, "unit": "image"}
    },
    {
        "name": "gpt-5-all",
        "category": "LLM",
        "description": "gpt-5-all是openai最新的旗舰模型",
        "pricing": {"input": 1.2500, "output": 10.0000, "unit": "M_tokens"}
    },
    {
        "name": "gpt-5-pro-all",
        "category": "LLM",
        "description": "gpt-5-pro-all 是openai 最新出的 顶尖模型",
        "pricing": {"unit_price": 1.610, "unit": "invocation"} # Special case, seems to be per-invocation
    }
]

def construct_import_payload():
    """
    Constructs the payload for the system API settings import endpoint.
    """
    settings_to_import = []
    # Assuming 1 USD = 7 CNY and 1 CNY = 100 credits
    USD_TO_CREDITS = 7 * 100

    for model_data in N1N_MODELS_DATA:
        # Base setting
        setting = {
            "name": model_data["name"],
            "category": model_data["category"],
            "provider": "n1n",
            "model": model_data["name"],
            "base_url": "https://api.n1n.ai/v1",
            "api_key": "YOUR_N1N_API_KEY", # IMPORTANT: Replace with a real key or a key pool reference
            "is_active": True,
            "deprecated": False,
            "config": {
                "supplier_info": {
                    "description": model_data["description"]
                }
            },
            "billing_rules": []
        }

        pricing = model_data["pricing"]
        
        if pricing["unit"] == "M_tokens":
            # Input pricing
            setting["billing_rules"].append({
                "metric_key": "prompt_tokens",
                "unit_type": "token",
                "cost": (pricing["input"] / 1_000_000) * USD_TO_CREDITS,
            })
            # Output pricing
            setting["billing_rules"].append({
                "metric_key": "completion_tokens",
                "unit_type": "token",
                "cost": (pricing["output"] / 1_000_000) * USD_TO_CREDITS,
            })
        elif pricing["unit"] in ["image", "video", "invocation"]:
             setting["billing_rules"].append({
                "metric_key": "invocations",
                "unit_type": "invocation",
                "cost": pricing["unit_price"] * USD_TO_CREDITS,
            })

        settings_to_import.append(setting)

    return {
        "provider": "n1n",
        "settings": settings_to_import,
        "delete_unmentioned": False # Set to True if you want to remove other 'n1n' models not in this list
    }

def main():
    """
    Main function to execute the import.
    """
    payload = construct_import_payload()
    
    # You might need to add authentication headers if your API is protected
    headers = {
        "Content-Type": "application/json",
        # "Authorization": "Bearer YOUR_ADMIN_TOKEN", 
    }

    print("--- Payload to be sent ---")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("--------------------------")

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/settings/system/manage/import",
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers=headers,
            timeout=60
        )
        response.raise_for_status()
        print("✅ Import successful!")
        print("Response:", response.json())

    except requests.exceptions.RequestException as e:
        print(f"❌ Import failed: {e}")
        if e.response:
            print("Status Code:", e.response.status_code)
            try:
                print("Response Body:", e.response.json())
            except json.JSONDecodeError:
                print("Response Body:", e.response.text)

if __name__ == "__main__":
    main()
