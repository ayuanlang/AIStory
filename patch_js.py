import re

with open('c:/AIStory/frontend/src/services/api.js', 'r', encoding='utf-8') as f:
    text = f.read()

def_llm = "export const asyncLLMPost = async (endpoint, payload, options = {}) => {"
new_llm = "export const asyncLLMPost = async (endpoint, payload, options = {}) => {\n    if (payload && payload.function_name) {\n        payload.system_api_id = Number(localStorage.getItem('func_api_' + payload.function_name)) || null;\n    }"
text = text.replace(def_llm, new_llm)

with open('c:/AIStory/frontend/src/services/api.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("patched api.js asyncLLMPost")
