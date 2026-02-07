

import requests
import json
import asyncio
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are an AI assistant for a Storyboard Editor application.
Your goal is to help the user edit, create, and manage storyboard projects.

You have access to the following tools:
1. `generate_project_asset`
   - Use this to generate images or videos.
   - Parameters:
     - `prompt`: (string) Description of the image/video.
     - `target_type`: (string) "shot" or "character".
     - `target_id`: (string, optional) ID of the shot/character if modifying an existing one.

2. `analyze_script`
   - Use this to analyze a script text.
   - Parameters:
     - `text`: (string) The script content.

3. `update_project_metadata`
   - Use this to change project title vs description.
   - Parameters:
     - `title`: (string, optional)
     - `description`: (string, optional)

RESPONSE FORMAT:
You must respond with a JSON object. Do not include markdown formatting (like ```json).
The JSON object must have exactly these keys:
- `reply`: (string) A conversational response to the user explaining what you are doing.
- `plan`: (array) A list of tool calls to execute.

Example Response:
{
    "reply": "I'll generate a cinematic shot of a rainy street.",
    "plan": [
        {
            "tool": "generate_project_asset",
            "parameters": {
                "prompt": "Cinematic wide angle shot of rainy street at night, cyberpunk style",
                "target_type": "shot"
            }
        }
    ]
}

If the user's request is not clear or does not require a tool, return an empty plan.
"""

class LLMService:
    async def analyze_intent(self, query: str, context: Dict[str, Any], history: List[Dict[str, str]], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes user query and returns a plan (list of tool calls).
        """
        if not config:
            # Fallback mock if no config
            logger.warning("No LLM config provided, using mock fallback.")
            return self._mock_fallback(query)

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             return {"reply": "Please configure your LLM API Key in Settings.", "plan": []}

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        
        # Add context summary to system message or valid context message
        context_str = f"Current Project Context: {json.dumps(context, default=str)}"
        messages.append({"role": "system", "content": context_str})

        # Add history
        for msg in history[-5:]: # Keep last 5 turns
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        
        # Add current query
        messages.append({"role": "user", "content": query})

        extra_config = config.get("config", {})

        try:
            return await self._call_openai_compatible(base_url, api_key, model, messages, extra_config)
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            return {
                "reply": f"Sorry, I encountered an error communicating with the AI provider: {str(e)}",
                "plan": []
            }


    async def chat_completion(self, messages: List[Dict], config: Dict[str, Any]) -> str:
        """
        Direct chat completion that returns raw content string.
        """
        if not config:
            raise ValueError("No LLM config provided")

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             raise ValueError("API Key missing in config")

        try:
            # Re-use the openai compatible caller but just extract content
            # This is a bit of a hack to reuse existing code which expects a specific JSON format
            # But the _call_openai_compatible method parses JSON for agents. 
            # We need a simpler caller for raw text generation.
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # OpenAI specific headers
            if "openai" in (base_url or "").lower():
                 pass 
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                # "stream": True # TODO: Support streaming?
            }
            if extra_config := config.get("config", {}):
                  # Merge extra config like max_tokens etc if needed
                  payload.update(extra_config)

            timeout = 300 # 5 minutes for long analysis
            
            logger.info(f"LLM Completion Request to {base_url} model {model}")
            
            # Using synchronous requests for simplicity in async wrapper, or use aiohttp
            # LLMService methods are async def, so we should run blocking IO in executor if using requests,
            # but for now let's just do a direct call. Since this runs in FastAPI async route, 
            # blocking here is bad. But _call_openai_compatible uses run_in_executor? 
            # Actually _call_openai_compatible logic below uses requests.post which blocks.
            # We should probably fix that broadly, but for now let's follow the pattern.
            
            response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content

        except Exception as e:
            logger.error(f"LLM Raw Completion failed: {e}")
            raise e

    async def _call_openai_compatible(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> Dict[str, Any]:
        content = await self._raw_llm_request(base_url, api_key, model, messages, extra_config)
        
        # Parse JSON from content
        # LLM might wrap in ```json ... ```
        clean_content = content.strip()
        if clean_content.startswith("```"):
            # Remove marked block
            lines = clean_content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_content = "\n".join(lines)
            
        try:
            result = json.loads(clean_content)
            # Validate keys
            if "reply" not in result:
                result["reply"] = clean_content
            if "plan" not in result:
                result["plan"] = []
            return result
        except json.JSONDecodeError:
            # Fallback if not valid JSON
            return {
                "reply": clean_content,
                "plan": [] # specific heuristics could be applied here
            }

    async def generate_content(self, prompt: str, system_prompt: str, config: Dict[str, Any]) -> str:
        if not config:
            return "Error: No LLM configuration found."

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             return "Error: Please configure your LLM API Key in Settings."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        extra_config = config.get("config", {})

        try:
            return await self._raw_llm_request(base_url, api_key, model, messages, extra_config)
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            return f"Error: {str(e)}"

    async def _raw_llm_request(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> str:
        # Ensure base_url ends with correct chat endpoint if not specific
        url = base_url
        if not url.endswith("/chat/completions"):
            # Handle trailing slash
            if url.endswith("/"):
                url = url + "chat/completions"
            elif "chat/completions" not in url:
                url = url + "/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": 0.7
        }

        if extra_config:
            # Merge extra config, but don't overwrite critical fields if not intended
            # For now, just update, but maybe exclude 'model' or 'messages'
            for k, v in extra_config.items():
                if k not in ["model", "messages", "stream"]:
                    payload[k] = v
        
        logger.info(f"Calling LLM: {url} model={model}")

        def _request(bypass_proxy=False):
            kwargs = {
                "json": payload,
                "headers": headers,
                "timeout": 120
            }
            if bypass_proxy:
                kwargs["proxies"] = {"http": None, "https": None}
            return requests.post(url, **kwargs)

        try:
            response = await asyncio.to_thread(_request, False)
        except (requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            logger.warning(f"Connection failed ({str(e)}). Retrying without proxy...")
            response = await asyncio.to_thread(_request, True)
        
        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}: {response.text}")

        data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        else:
             raise Exception(f"Invalid API Response: {data}")

    def _mock_fallback(self, query: str) -> Dict[str, Any]:
        if "analyze" in query.lower():
            return {
                "reply": "I will analyze the script (Mock).",
                "plan": [{"tool": "analyze_script", "parameters": {"text": "..."}}]
            }
        return {"reply": f"Mock reply to: {query}", "plan": []}

llm_service = LLMService()
