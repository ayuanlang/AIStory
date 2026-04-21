import json
import os
config_path = c:/AS/AIStory/backend/queue_config.json
def get_config():
    if os.path.exists(config_path):
        with open(config_path, r) as f:
            return json.load(f)
    return {queue_threads: 20, callback_threads: 20}
def save_config(queue_threads, callback_threads):
    with open(config_path, w) as f:
        json.dump({queue_threads: queue_threads, callback_threads: callback_threads}, f)
