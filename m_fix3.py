import re  
with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f: content = f.read()  
content = re.sub(r'            if len\(resolved_image_refs\) \                for item in resolved_image_refs\[1:\]:.*?                    content_payload\.append\(\{.*?                        \" "type\: \image_url\,.*?                        \image_url\: \{\url\: item\},.*?                        \role\: \reference_image\,.*?                    \}\).*?            elif resolved_image_refs:', r'            if resolved_image_refs:', content, flags=re.DOTALL)  
with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f: f.write(content)  ; python m_fix3.py ; del m_fix3.py
