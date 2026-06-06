import asyncio
from fastapi import FastAPI, BackgroundTasks
import uvicorn
import httpx
import threading

app = FastAPI()

async def bg_task(u_id):
    print(f"Executing bg_task for u_id {u_id}")
    await asyncio.sleep(1)
    print("Done bg_task")

@app.get("/")
def endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(bg_task, 123)
    return {"status": "ok"}

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")

threading.Thread(target=run_server, daemon=True).start()
import time
time.sleep(2)
r = httpx.get("http://127.0.0.1:8001/")
print("Response:", r.json())
time.sleep(2)
