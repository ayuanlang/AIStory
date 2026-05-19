data=open('C:/AS/AIStory/backend/app/services/llm_service.py', encoding='utf-8').read(); idx = data.find('LLM_RESPONSE_SUMMARY'); print(data[idx-800:idx+500])
