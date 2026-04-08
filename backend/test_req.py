from app.api.endpoints import GenerationRequest
import sys, json

payload = {"prompt": "x", "mode": "joint_diptych"}
req = GenerationRequest(**payload)

print(getattr(req, "mode", "NONE"))
