import json

def patch3():
    file_path = '../backend/app/api/endpoints.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    idx = [i for i, l in enumerate(lines) if '_release_db_connection(db, "analyze_scene_llm_call")' in l][0]
    
    insert_idx = idx + 1
    
    code_to_insert = """
        if is_stream:
            from app.services.llm_service import _raw_llm_request_stream
            async def event_generator():
                try:
                    async for chunk in _raw_llm_request_stream(current_messages, config):
                        if chunk and chunk.get("type") == "token":
                            yield f"data: {json.dumps({'text': chunk.get('content', '')})}\\n\\n"
                    
                    yield "data: [DONE]\\n\\n"
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    yield f"data: {json.dumps({'text': f'Error: {e}'})}\\n\\n"
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
"""
    
    lines = lines[:insert_idx] + [code_to_insert] + lines[insert_idx:]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

patch3()