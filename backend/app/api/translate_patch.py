class TranslatePromptRequest(BaseModel):
    q: str
    from_lang: str = "zh"
    to_lang: str = "en"

@router.post("/tools/translate_prompt")
async def translate_prompt_llm(
    req: TranslatePromptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(translate_prompt_llm, user_id=current_user.id, kind="translate_prompt",
                            req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    
    request_id = uuid.uuid4().hex[:12]
    import time
    timestamp = int(time.time())
    text = str(req.q or "").strip()
    from_lang = str(req.from_lang or "zh").strip()
    to_lang = str(req.to_lang or "en").strip()

    if not text:
        return {"translated_text": ""}

    llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM")
    if not llm_config or not llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="Active LLM Settings not found.")

    provider = llm_config.get("provider") or "llm"
    model = llm_config.get("model") or "unknown"

    reservation_tx = None
    try:
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            est = billing_service.estimate_input_output_tokens_from_messages(
                [{"role": "user", "content": text}],
                output_ratio=1.0
            )
            reserve_details = {
                "item": "translate_prompt", "request_id": request_id, 
                "chars": len(text), "provider": provider, "model": model
            }
            reservation_tx = billing_service.reserve_balance(
                db, current_user.id, est["estimated_total_price"], 
                reserve_details, provider, model
            )
            if not reservation_tx:
                raise HTTPException(status_code=402, detail="Insufficient balance.")
    except HTTPException:
        raise
    except Exception as e:
         logger.error(f"[translate] pre-billing failed: {e}")
         raise HTTPException(status_code=500, detail="Billing precheck failed.")

    target_lang_display = "English" if to_lang == "en" else "Simplified Chinese"
    source_lang_display = "Simplified Chinese" if from_lang == "zh" else "English"

    system_prompt = (
        f"You are a professional prompt translator. Your task is to translate the {source_lang_display} prompt to {target_lang_display}. "
        "CRITICAL RULES: \n"
        "1. Just return the translated text EXACTLY preserving the original format (commas, newlines, parenthetical weights like (word:1.2), brackets, tags).\n"
        "2. DO NOT add any extra conversational text, explanation, or notes. \n"
        "3. DO NOT add or remove semantic content. Do not change the original meaning.\n"
        "4. Output ONLY the raw translated valid prompt string."
    )

    user_prompt = f"Text to translate:\n{text}"

    try:
        response_text, call_metrics = agent_service.call_llm_agent(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            api_config=llm_config,
            temperature=0.0
        )
        translated_text = response_text.strip()
        
        if reservation_tx:
            try:
                settle_details = {
                    "item": "translate_prompt",
                    "request_id": request_id,
                    **call_metrics
                }
                billing_service.settle_reserved_balance(
                    db, current_user.id, reservation_tx.tx_id, 
                    call_metrics["total_price"], settle_details
                )
            except Exception as settle_e:
                logger.error(f"[translate_prompt] settle failed: {settle_e}")

        return {"translated_text": translated_text, "request_id": request_id}
    except Exception as e:
        logger.error(f"[translate_prompt] failed: {e}")
        if reservation_tx:
            try:
                billing_service.release_reserved_balance(db, current_user.id, reservation_tx.tx_id)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))
