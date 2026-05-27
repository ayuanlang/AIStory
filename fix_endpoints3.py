import re

with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'rb') as f:
    data = f.read()

# find what bytes it is.
# look for "供应商调用失
prefix = "供应商调用失".encode('utf-8')
idx = data.find(prefix)
if idx != -1:
    print("Found! bytes around:")
    print(data[max(0, idx-10):idx+30])

c_in = b' in detail:'
idx2 = data.find(c_in, idx)
if idx2 != -1:
    print("Found 'in detail:' at", idx2)

# Just replace line 3217 from  the beginning
def patch(data):
    lines = data.split(b'\n')
    for i, line in enumerate(lines):
        if b'def _vendor_failed_message' in line:
            return i
    return -1

i = patch(data)
if i != -1:
    lines = data.split(b'\n')
    # just rewrite the whole function
    new_func = [
        b'def _vendor_failed_message(provider: Optional[str], reason: Any) -> str:\r',
        b'    vendor = str(provider or "").strip() or "unknown"\r',
        b'    detail = str(reason or "unknown error").strip()\r',
        b'    if "\xe4\xbe\x9b\xe5\xba\x94\xe5\x95\x86\xe8\xb0\x83\xe7\x94\xa8\xe5\xa4\xb1\xe8\xb4\xa5" in detail:\r', # 供应商调用失败
        b'        return detail\r',
        b'    return f"{vendor}\xe4\xbe\x9b\xe5\xba\x94\xe5\x95\x86\xe8\xb0\x83\xe7\x94\xa8\xe5\xa4\xb1\xe8\xb4\xa5: {detail}"\r',
        b'\r'
    ]
    # delete lines i to i+6
    lines[i:i+6] = new_func

    with open(r'c:\AS\AIStory\backend\app\api\endpoints.py', 'wb') as f:
        f.write(b'\n'.join(lines))

