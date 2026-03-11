import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests


def _build_url(base_url: str, model: str) -> str:
    root = (base_url or "https://api.kie.ai").strip().rstrip("/")
    return f"{root}/{model}/v1/chat/completions"


def _build_messages(user_text: str, image_url: Optional[str]) -> List[Dict[str, Any]]:
    if image_url:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                        },
                    },
                    {
                        "type": "text",
                        "text": user_text,
                    },
                ],
            }
        ]
    return [{"role": "user", "content": user_text}]


def _build_payload(model: str, messages: List[Dict[str, Any]], stream: bool) -> Dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "stream": stream,
        "tools": [{"googleSearch": {}}],
        "include_thoughts": True,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"}
                    },
                    "required": ["answer"]
                }
            }
        },
    }


def _extract_chunk_text(chunk: Dict[str, Any]) -> str:
    choices = chunk.get("choices") or []
    if not choices:
        return ""

    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        return "".join(text_parts)
    return ""


def _stream_request(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int) -> Tuple[str, Optional[Dict[str, Any]]]:
    response = requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout)
    if response.status_code != 200:
        body = response.text[:1200]
        raise RuntimeError(f"HTTP {response.status_code}: {body}")

    text_parts: List[str] = []
    usage: Optional[Dict[str, Any]] = None

    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue

        data_str = line[5:].strip()
        if data_str == "[DONE]":
            break

        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        if isinstance(chunk.get("usage"), dict):
            usage = chunk["usage"]

        token_text = _extract_chunk_text(chunk)
        if token_text:
            text_parts.append(token_text)
            print(token_text, end="", flush=True)

    print()
    return "".join(text_parts), usage


def _full_request(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int) -> Tuple[str, Optional[Dict[str, Any]]]:
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if response.status_code != 200:
        body = response.text[:1200]
        raise RuntimeError(f"HTTP {response.status_code}: {body}")

    data = response.json()
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else None

    answer = ""
    choices = data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            answer = content
        elif isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            answer = "".join(parts)

    print(answer)
    return answer, usage


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Minimal KIE chat/completions verifier for stream/tools/include_thoughts/json_schema",
    )
    parser.add_argument("--api-key", required=True, help="KIE API key")
    parser.add_argument("--model", default="gemini-2.5-flash", help="KIE model in URL path")
    parser.add_argument("--base-url", default="https://api.kie.ai", help="KIE API root")
    parser.add_argument("--text", default="Please answer in one JSON object with key 'answer'.", help="User text")
    parser.add_argument("--image-url", default="", help="Optional image URL for multimodal message")
    parser.add_argument("--stream", action="store_true", help="Use streaming mode")
    parser.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds")

    args = parser.parse_args()

    url = _build_url(args.base_url, args.model)
    messages = _build_messages(args.text, args.image_url or None)
    payload = _build_payload(args.model, messages, stream=args.stream)

    headers = {
        "Authorization": f"Bearer {args.api_key}",
        "Content-Type": "application/json",
    }

    print("=== KIE Request Target ===")
    print(url)
    print("=== Payload Flags ===")
    print(
        json.dumps(
            {
                "stream": payload.get("stream"),
                "has_tools": bool(payload.get("tools")),
                "include_thoughts": payload.get("include_thoughts"),
                "response_format_type": (payload.get("response_format") or {}).get("type"),
                "has_image": bool(args.image_url),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("=== Model Output ===")

    try:
        if args.stream:
            answer, usage = _stream_request(url, headers, payload, timeout=args.timeout)
        else:
            answer, usage = _full_request(url, headers, payload, timeout=args.timeout)
    except Exception as exc:
        print(f"[FAIL] request error: {exc}")
        return 1

    print("=== Verification Summary ===")
    checks = {
        "stream_requested": bool(payload.get("stream")),
        "tools_sent": bool(payload.get("tools")),
        "include_thoughts_sent": payload.get("include_thoughts") is True,
        "json_schema_sent": ((payload.get("response_format") or {}).get("type") == "json_schema"),
        "response_non_empty": bool(str(answer or "").strip()),
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))

    if usage:
        print("=== Usage ===")
        print(json.dumps(usage, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
