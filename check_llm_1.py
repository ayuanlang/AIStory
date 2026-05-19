data = open('C:/AS/AIStory/backend/app/services/llm_service.py', encoding='utf-8').read()
idx = data.find('async for chunk in self._raw_llm_request_stream')
print(data[max(0, idx-1000):idx+2500])