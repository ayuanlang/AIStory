import urllib.request
req = urllib.request.Request('https://open.volcengineapi.com/?Action=CreateAssetGroup&Version=2024-12-01', method='POST', headers={'Content-Type': 'application/json'})
try:
    urllib.request.urlopen(req)
except Exception as e:
    print(e.read())