import urllib.request, urllib.error, socket

socket.setdefaulttimeout(5)
out = []

# Write start marker
with open('_test_out.txt', 'w') as f:
    f.write('STARTED\n')

# Test /users/me
try:
    req = urllib.request.Request('http://127.0.0.1:8000/users/me', headers={'Authorization': 'Bearer invalid'})
    resp = urllib.request.urlopen(req, timeout=5)
    out.append(f"users/me STATUS: {resp.status}")
except urllib.error.HTTPError as e:
    out.append(f"users/me STATUS: {e.code} BODY: {e.read().decode()[:300]}")
except Exception as e:
    out.append(f"users/me ERROR: {type(e).__name__}: {e}")

# Test /settings
try:
    req2 = urllib.request.Request('http://127.0.0.1:8000/settings')
    resp2 = urllib.request.urlopen(req2, timeout=5)
    out.append(f"settings STATUS: {resp2.status}")
except urllib.error.HTTPError as e2:
    out.append(f"settings STATUS: {e2.code} BODY: {e2.read().decode()[:300]}")
except Exception as e2:
    out.append(f"settings ERROR: {type(e2).__name__}: {e2}")

# Test /docs (sanity check)
try:
    req3 = urllib.request.Request('http://127.0.0.1:8000/docs')
    resp3 = urllib.request.urlopen(req3, timeout=5)
    out.append(f"docs STATUS: {resp3.status}")
except urllib.error.HTTPError as e3:
    out.append(f"docs STATUS: {e3.code}")
except Exception as e3:
    out.append(f"docs ERROR: {type(e3).__name__}: {e3}")

with open('_test_out.txt', 'w') as f:
    f.write('\n'.join(out))
