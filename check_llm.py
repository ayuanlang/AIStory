data = open('C:/AS/AIStory/backend/app/services/llm_service.py', encoding='utf-8').read()
idx = data.find('LLM_RESPONSE"')
print(data[max(0, idx-500):idx+500])