
import asyncio
import httpx
async def main():
    b2_url = 'https://s3.us-east-005.backblazeb2.com/aistory/1/generated/edc78fe365371e95.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=005fabbd055b11f0000000001%2F20260405%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20260405T155823Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=ae67b3350f95ea2f9122130f83d9baa2bf1b32751d7405ccd49e479f67044f58'
    async with httpx.AsyncClient() as client:
        resp = await client.get(b2_url, follow_redirects=True, timeout=30.0)
        print('STATUS:', resp.status_code)

asyncio.run(main())

