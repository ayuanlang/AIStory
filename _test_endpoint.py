import urllib.request
import urllib.error

result_file = r'c:\storyboard\AIStory\_test_result.txt'

try:
    rq = urllib.request.Request(
        'http://localhost:8000/api/v1/users/me',
        headers={'Authorization': 'Bearer test'}
    )
    resp = urllib.request.urlopen(rq)
    with open(result_file, 'w') as f:
        f.write(f'OK {resp.status}')
except urllib.error.HTTPError as e:
    body = e.read().decode()[:300]
    with open(result_file, 'w') as f:
        f.write(f'ERR {e.code} {body}')
except Exception as e:
    with open(result_file, 'w') as f:
        f.write(f'EXCEPTION {e}')
