import boto3
from botocore.config import Config

def test_b2():
    pool_endpoint = 'https://s3.us-east-005.backblazeb2.com'
    access_key = '005fabbd055b11f0000000001'
    secret_key = '00599064c7c26f79cc780b539907cb23242e40534f'
    region = 'us-east-005'
    bucket = 'aistory'

    for force_path in [True, False]:
        for sig in ['s3v4', None]:
            print(f'\n--- Testing force_path_style={force_path}, signature={sig} ---')
            config_kwargs = {}
            if sig:
                config_kwargs['signature_version'] = sig
            config_kwargs['s3'] = {'addressing_style': 'path' if force_path else 'virtual'}
            
            client = boto3.client(
                's3',
                endpoint_url=pool_endpoint,
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=Config(**config_kwargs)
            )
            try:
                client.put_object(Bucket=bucket, Key='test_diag.txt', Body=b'test')
                print('Success!')
            except Exception as e:
                print(f'Error: {e}')

if __name__ == '__main__':
    test_b2()
