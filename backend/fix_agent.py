import sys

path = 'c:/AS/AIStory/backend/app/services/agent_service.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

o1 = """            async for event in llm_service.stream_analyze_intent(
                request.query, request.context, request.history, llm_config
            ):
                if event.get("type") == "token":
                    token_count += 1
                    if token_count <= 3:
                        print(f"[STREAM-DEBUG] agent_service: received token #{token_count}: {repr(event.get('content','')[:50])}")
                    yield event
                elif event.get("type") == "result":
                    print(f"[STREAM-DEBUG] agent_service: received result event, reply_len={len(str(event.get('reply','')))}, plan_len={len(event.get('plan',[]))}")
                    llm_result = event
                    yield event
                else:
                    yield event"""

n1 = """            from contextlib import aclosing
            async with aclosing(llm_service.stream_analyze_intent(
                request.query, request.context, request.history, llm_config
            )) as _stream:
                async for event in _stream:
                    if event.get("type") == "token":
                        token_count += 1
                        if token_count <= 3:
                            print(f"[STREAM-DEBUG] agent_service: received token #{token_count}: {repr(event.get('content','')[:50])}")
                        yield event
                    elif event.get("type") == "result":
                        print(f"[STREAM-DEBUG] agent_service: received result event, reply_len={len(str(event.get('reply','')))}, plan_len={len(event.get('plan',[]))}")
                        llm_result = event
                        yield event
                    else:
                        yield event"""

text = text.replace(o1, n1)

o2 = """        async for event in llm_service.stream_analyze_intent_with_system_prompt(
            request.query, merged_context, request.history or [],
            llm_config, self._SYSTEM_MANAGEMENT_PROMPT,
        ):
            if event.get("type") == "token":
                yield event
            elif event.get("type") == "result":
                llm_result = event
                yield event
            else:
                yield event"""

n2 = """        from contextlib import aclosing
        async with aclosing(llm_service.stream_analyze_intent_with_system_prompt(
            request.query, merged_context, request.history or [],
            llm_config, self._SYSTEM_MANAGEMENT_PROMPT,
        )) as _stream:
            async for event in _stream:
                if event.get("type") == "token":
                    yield event
                elif event.get("type") == "result":
                    llm_result = event
                    yield event
                else:
                    yield event"""

text = text.replace(o2, n2)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
