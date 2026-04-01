import boto3

def test_b2():
    client = boto3.client(
        's3',
        endpoint_url='https://s3.us-east-005.backblazeb2.com',
        region_name='us-east-1',
        aws_access_key_id='005fabbd055b11f0000000001',
        aws_secret_access_key='00599064c7c26f79cc780b539907cb23242e40534f'
    )
    try:
        res = client.list_buckets()
        print('Buckets:', [b['Name'] for b in res['Buckets']])
    except Exception as e:
        print(f'Error listing buckets: {e}')

if __name__ == '__main__':
    test_b2()
