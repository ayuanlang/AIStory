

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
    async def analyze_multimodal(self, prompt: str, image_url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes an image with a prompt using multimodal LLM capabilities.
        Returns Dict with 'content' and 'usage'.
        Supports:
        1. Doubao/Ark format (if 'doubao' in model name or 'responses' endpoint used)
        2. Standard OpenAI Vision format (fallback)
        """
        if not config:
            return {"content": "Error: No LLM configuration found.", "usage": {}}

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             return {"content": "Error: Please configure your LLM API Key in Settings.", "usage": {}}

        # Detect Doubao / Ark specific mode based on user instruction
        is_doubao = "doubao" in (model or "").lower() or "ark.cn-" in (base_url or "").lower()

        if is_doubao:
            return await self._call_doubao_prop(base_url, api_key, model, prompt, image_url)
        else:
            return await self._call_openai_vision(base_url, api_key, model, prompt, image_url)

    async def _call_doubao_prop(self, base_url: str, api_key: str, model: str, prompt: str, image_url: str) -> Dict[str, Any]:
        """
        Specific implementation for Doubao/Ark /api/v3/responses endpoint
        Structure:
        {
            "model": "...",
            "input": [ { "role": "user", "content": [ { "type": "input_image", ... }, { "type": "input_text", ... } ] } ]
        }
        """
        # Construct specific Doubao URL
        # base_url usually: https://ark.cn-beijing.volces.com/api/v3
        url = base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            url = url.replace("/chat/completions", "/responses")
        elif not url.endswith("/responses"):
             url = f"{url}/responses"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": image_url
                        },
                        {
                            "type": "input_text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }
        
        logger.info(f"Calling Doubao Multimodal: {url} model={model}")

        def _request():
            return requests.post(url, headers=headers, json=payload, timeout=120)

        try:
            response = await asyncio.to_thread(_request)
            
            if response.status_code != 200:
                 # Try fallback to standard OpenAI format if 404/400, in case it's a standard model
                 logger.warning(f"Doubao proprietary call failed: {response.text}. Attempting OpenAI standard format...")
                 return await self._call_openai_vision(base_url, api_key, model, prompt, image_url)
                 
            data = response.json()
            # Doubao responses format might differ?
            # Usually Ark /responses returns similar to /chat/completions but 'choices' key exists
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {"content": content, "usage": usage}
            else:
                 return {"content": f"Error: Unexpected response format from Doubao: {data}", "usage": {}}
                 
        except Exception as e:
            logger.error(f"Doubao Multimodal failed: {e}")
            return {"content": f"Error: {e}", "usage": {}}

    async def _call_openai_vision(self, base_url: str, api_key: str, model: str, prompt: str, image_url: str) -> Dict[str, Any]:
        """Standard OpenAI Vision Format"""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text", 
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ]
        
        # Reuse existing raw request logic but we need to ensure it processes the list content correctly
        # The existing _raw_llm_request takes `messages` list and sends it as JSON.
        # So it should simply work if we call it.
        try:
             # Use _raw_llm_request_full to get usage
             full_response = await self._raw_llm_request_full(base_url, api_key, model, messages)
             content = full_response["choices"][0]["message"]["content"]
             usage = full_response.get("usage", {})
             return {"content": content, "usage": usage}
        except Exception as e:
             logger.error(f"OpenAI Vision call failed: {e}")
             return {"content": f"Error: {e}", "usage": {}}

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


    async def chat_completion(self, messages: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Direct chat completion that returns Dict with 'content' and 'usage'.
        """
        if not config:
            raise ValueError("No LLM config provided")

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             raise ValueError("API Key missing in config")

        extra_config = config.get("config", {})

        try:
            full_response = await self._raw_llm_request_full(base_url, api_key, model, messages, extra_config)
            content = full_response["choices"][0]["message"]["content"]
            usage = full_response.get("usage", {})
            return {"content": content, "usage": usage}
        except Exception as e:
            logger.error(f"LLM Raw Completion failed: {e}")
            raise e

    async def _call_openai_compatible(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> Dict[str, Any]:
        full_response = await self._raw_llm_request_full(base_url, api_key, model, messages, extra_config)
        content = full_response["choices"][0]["message"]["content"]
        usage = full_response.get("usage", {})
        
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
            
            # Inject Usage
            result["usage"] = usage
            return result

        except json.JSONDecodeError:
            # Fallback if not valid JSON
            return {
                "reply": clean_content,
                "plan": [],
                "usage": usage
            }


    async def generate_content(self, prompt: str, system_prompt: str, config: Dict[str, Any]) -> Dict[str, Any]:
        if not config:
            return {"content": "Error: No LLM configuration found.", "usage": {}}

        api_key = config.get("api_key")
        base_url = config.get("base_url")
        model = config.get("model")

        if not api_key:
             return {"content": "Error: Please configure your LLM API Key in Settings.", "usage": {}}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        extra_config = config.get("config", {})

        try:
            full_response = await self._raw_llm_request_full(base_url, api_key, model, messages, extra_config)
            content = full_response["choices"][0]["message"]["content"]
            usage = full_response.get("usage", {})
            return {"content": content, "usage": usage}
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            return {"content": f"Error: {str(e)}", "usage": {}}

    async def _raw_llm_request(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> str:
        data = await self._raw_llm_request_full(base_url, api_key, model, messages, extra_config)
        return data["choices"][0]["message"]["content"]

    async def _raw_llm_request_full(self, base_url: str, api_key: str, model: str, messages: List[Dict], extra_config: Dict[str, Any] = None) -> Dict[str, Any]:
        # Ensure base_url ends with correct chat endpoint if not specific
        if not base_url:
             base_url = "https://api.openai.com/v1" # Default to OpenAI if not set
             
        url = base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
             url = f"{url}/chat/completions"
        
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
        print(f"Calling LLM DIRECT PRINT: {url} model={model}", flush=True)

        # Debug Payload (Masking potentially large image data if we were sending base64, but here it is URL)
        import copy
        debug_payload = copy.deepcopy(payload)
        if "messages" in debug_payload:
            for m in debug_payload["messages"]:
                 if isinstance(m.get("content"), list):
                      for c in m["content"]:
                           if isinstance(c, dict) and c.get("type") == "image_url":
                                # Truncate long data urls if any
                                url_val = c.get("image_url", {}).get("url", "")
                                if url_val and url_val.startswith("data:"):
                                     c["image_url"]["url"] = url_val[:50] + "...(truncated)"
        
        logger.info(f"LLM Payload Body: {json.dumps(debug_payload, ensure_ascii=False)}")

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
        print(f"LLM Response DIRECT PRINT: {json.dumps(data, ensure_ascii=False)}", flush=True)
        # Also log
        logging.getLogger("app").info(f"LLM Response: {json.dumps(data, ensure_ascii=False)}")
        
        if "choices" in data and len(data["choices"]) > 0:
            return data
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
