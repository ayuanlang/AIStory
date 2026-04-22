# -*- coding: utf-8 -*-
import re
filepath = "C:/AS/AIStory/backend/app/services/oss_storage_service.py"
with open(filepath, "r", encoding="utf-8") as f:
    text = f.read()

old_str = """            if getattr(pool, "default_storage_class", None):
                extra["StorageClass"] = str(pool.default_storage_class)

            try:
                _visible_info("""

new_str = """            if getattr(pool, "default_storage_class", None):
                st_class = str(pool.default_storage_class)
                provider_nm = str(getattr(pool, "provider", "")).lower()
                if provider_nm == "backblaze" and st_class == "STANDARD_IA":
                    pass
                else:
                    extra["StorageClass"] = st_class

            try:
                _visible_info("""

text = text.replace(old_str, new_str)
with open(filepath, "w", encoding="utf-8") as f:
    f.write(text)
print("Patched!")
