import os
import requests
from volcenginesdkcore.signv4 import SignerV4

os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

hdrs = {'Content-Type': 'application/json', 'Host': 'ark.volcengineapi.com'}
body = '{}'
SignerV4.sign('/', 'POST', hdrs, body, None, {'Action': 'CreateAssetGroup', 'Version': '2024-12-01'}, 'AK', 'SK', 'cn-beijing', 'ark')
r = requests.post('https://ark.volcengineapi.com/?Action=CreateAssetGroup&Version=2024-12-01', headers=hdrs, data=body)
print(r.status_code, r.text)
