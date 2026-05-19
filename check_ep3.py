data = open('C:/AS/AIStory/backend/app/api/endpoints.py', encoding='utf-8').read()
idx = data.find('dedup_total_chars_dict')
print(data[max(0, idx-1000):idx+100])