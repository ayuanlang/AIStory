import re
import uuid
import json
import asyncio
import logging
import requests
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

def _debug_log(msg):
    logger.debug(msg)

def _strip_base64_from_log(payload):
    try:
        s = str(payload)
        if len(s) > 200:
            return s[:200] + '... [truncated]'
        return s
    except Exception:
        return ""

file_path = 'backend/app/services/zlhub_gen.py'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
out = []
for line in lines:
    if line.startswith('async def ') or line.startswith('def '):
        out.append('    ' + line)
    else:
        out.append(line)

imports = """import re
import uuid
import json
import asyncio
import logging
import requests
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

def _debug_log(msg):
    logger.debug(msg)

def _strip_base64_from_log(payload):
    try:
        s = str(payload)
        if len(s) > 200:
            return s[:200] + '... [truncated]'
        return s
    except Exception:
        return \"\"

class ZlhubMixin:
"""

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(imports + '\n'.join(out))
