import json

def _extract_first_json_payload(text: str):
    decoder = json.JSONDecoder()
    candidates = []
    for idx, ch in enumerate(text):
        if ch in "[{":
            candidates.append(idx)

    for start in candidates:
        try:
            obj, _end = decoder.raw_decode(text[start:])
            if isinstance(obj, (dict, list)):
                return obj
        except Exception:
            continue
    return None

test_text = """{
    "name": "Test",
    "attributes": {},
    "trailing": "comma",
}"""

print("Testing text:")
print(test_text)
print("----------------")
result = _extract_first_json_payload(test_text)
print("Extracted result:", result)
