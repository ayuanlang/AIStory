with open('backend/app/services/media_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

s1_old = '''              if ref_mode == " entity_refs\:
 payload[\imageUrls\] = image_refs
 # Some API may still need the first_image
 if primary_field not in [\imageUrls\]:
 payload[primary_field] = first_image
 else:'''

s1_new = ''' if ref_mode == \entity_refs\:
 if \/openapi/v2/rhart-video\ in endpoint_lower and \/multimodal-video\ not in endpoint_lower:
 if \sparkvideo\ in submit_url.lower():
 submit_url = submit_url.replace(\/image-to-video\, \/multimodal-video\)
 endpoint_lower = submit_url.lower()

 unique_refs = []
 seen = set()
 for x in image_refs:
 base = x.split('?')[0]
 if base not in seen:
 seen.add(base)
 unique_refs.append(x)

 payload[\imageUrls\] = unique_refs
 # Some API may still need the first_image
 if primary_field not in [\imageUrls\]:
 payload[primary_field] = first_image
 else:'''

text = text.replace(s1_old, s1_new, 1)

with open('backend/app/services/media_service.py', 'w', encoding='utf-8') as f:
 f.write(text)

print(\SUCCESS\)
