data = open('C:/AS/AIStory/backend/app/api/endpoints.py', encoding='utf-8').read()
idx = data.find('LLM_STREAM_INCOMPLETE_REJECTED')
print(data[max(0, idx-500):idx+500])