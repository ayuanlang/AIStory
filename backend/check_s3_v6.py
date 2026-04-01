import boto3
from botocore.config import Config

def test_b2():
    pool_endpoint = 'https://s3.us-east-005.backblazeb2.com'
    access_key = '005fabbd055b11f0000000001'
    secret_key = 'K005YvvF10NCnxZW5P8mg9IDbvf4Y44'
    region = 'us-east-005'
    bucket = 'aistory'

    # The region fix we did
    client = boto3.client(
        's3',
        endpoint_url=pool_endpoint,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'})
    )
    try:
        client.put_object(Bucket=bucket, Key='test_diag.txt', Body=b'test')
        print('Upload Success!')
        
        # Test List Buckets
        res = client.list_buckets()
        print('Buckets:', [b['Name'] for b in res['Buckets']])
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    test_b2()
