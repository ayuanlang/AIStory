data = open('C:/AS/AIStory/backend/app/services/llm_service.py', encoding='utf-8').read()
idx = data.find('_raw_llm_request_stream(')
print(data[idx:idx+2500])