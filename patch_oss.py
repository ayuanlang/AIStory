with open("backend/app/services/oss_storage_service.py", "r", encoding="utf-8") as f:
    text = f.read()

target1 = '''        if "://" in public_base_url:
            if is_qiniu and public_base_url.startswith("https://"):
                return public_base_url.replace("https://", "http://", 1)        
            return public_base_url'''

replacement1 = '''        if "://" in public_base_url:
            return public_base_url'''

target2 = '''        if is_qiniu:
            return f"http://{public_base_url}"'''

replacement2 = '''        if is_qiniu:
            return f"https://{public_base_url}"'''

target3 = '''        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": pool.bucket, "Key": key},
                ExpiresIn=int(getattr(pool, "presign_expires_seconds", 7 * 24 * 3600)),
            )
            if self._is_qiniu_provider(pool) and url.startswith("https://"):
                url = url.replace("https://", "http://", 1)
            return url
        except Exception as exc:'''

replacement3 = '''        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": pool.bucket, "Key": key},
                ExpiresIn=int(getattr(pool, "presign_expires_seconds", 7 * 24 * 3600)),
            )
            return url
        except Exception as exc:'''

if target1 in text:
    text = text.replace(target1, replacement1)
if target2 in text:
    text = text.replace(target2, replacement2)
if target3 in text:
    text = text.replace(target3, replacement3)

with open("backend/app/services/oss_storage_service.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Patch applied for OSS HTTPS")