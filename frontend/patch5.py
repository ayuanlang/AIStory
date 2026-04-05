def patch5():
    file_path = '../backend/app/api/endpoints.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    idx = [i for i, l in enumerate(lines) if '_release_db_connection(db,' in l][0]
    insert_idx = idx + 2
    
    code = """        if is_stream:
            from app.services.llm_service import llm_service
            
            async def event_generator():
                nonlocal current_messages
                try:
                    stream = llm_service._raw_llm_request_stream(
                        base_url=config.get("base_url"),
                        api_key=config.get("api_key"),
                        model=config.get("model"),
                        messages=current_messages,
                        extra_config=config
                    )
                    async for chunk in stream:
                        if chunk and chunk.get("type") == "token":
                            yield f"data: {json.dumps({'text': chunk.get('content', '')})}\\n\\n"
                    
                    yield "data: [DONE]\\n\\n"
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    yield f"data: {json.dumps({'text': f'Error: str(e)'})}\\n\\n"
            
            from starlette.responses import StreamingResponse
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
"""
    
    lines.insert(insert_idx, code)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

patch5()