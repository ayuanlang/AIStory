# -*- coding: utf-8 -*-
"""Section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.assets_pkg import shared as _shared

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)


from app.schemas.media_analyze import AnalyzeImageRequest  # noqa: E402,F401

# --- assets analyze ---
@router.post("/assets/analyze", response_model=Dict[str, str])
async def analyze_asset_image(
    request: AnalyzeImageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes an asset image to extract style and prompt descriptions.
    """
    asset = None
    image_url_raw = str(getattr(request, "image_url", "") or "").strip()
    if request.asset_id is not None:
        asset = db.query(Asset).filter(Asset.id == request.asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        if asset.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Not authorized")

        image_url_raw = str(asset.url or "").trim() if False else str(asset.url or "").strip()

    if not image_url_raw:
        raise HTTPException(status_code=400, detail="Asset id or image_url is required")

    # Asset style/prompt reverse always uses the script_analysis Function API dropdown.
    llm_config, selected_dropdown_id, _, _ = _resolve_script_analysis_dropdown_llm_config(
        db,
        current_user.id,
        "script_analysis",
        getattr(request, "system_api_id", None),
        context="analyze_asset_image",
    )
    api_provider = str(llm_config.get("provider") or "").strip()
    api_model = str(llm_config.get("model") or "").strip()
    if not api_provider or not api_model:
        raise HTTPException(status_code=400, detail="Script analysis API dropdown has no usable Vision/LLM model. Please configure it in Function APIs.")

    reservation_tx = None
    # Billing Check (token rules will be reserved later once we have final prompt/messages)
    if not billing_service.is_token_pricing(db, "analysis", api_provider, api_model):
        cost = billing_service.estimate_cost(db, "analysis", api_provider, api_model)
        billing_service.check_can_proceed(current_user, cost)

    llm_config = {
        "provider": api_provider,
        "api_key": llm_config.get("api_key"),
        "base_url": llm_config.get("base_url"),
        "model": api_model,
        "config": {
            **((llm_config.get("config") if isinstance(llm_config.get("config"), dict) else {}) or {}),
            "response_format": {"type": "json_object"},
            "include_thoughts": False,
            "__selected_system_api_id": selected_dropdown_id,
        }
    }

    # 3. Load System Prompt
    try:
        system_prompt = _resolve_prompt_text("image_style_extractor.txt")
    except FileNotFoundError:
        system_prompt = "Describe the art style and visual elements of this image."

    # 4. Construct Image URL
    base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")

    if image_url_raw and image_url_raw.startswith("http"):
        image_url_raw = _refresh_managed_media_url(image_url_raw, db)
        # Check if it is localhost and we are not in a local env (heuristic)
        # If the backend is local and the LLM is remote, the LLM cannot see 'localhost'.
        # We must assume the LLM cannot access localhost.
        # For production/render, RENDER_EXTERNAL_URL should be set.
        # For local dev with remote LLM, we might need to upload the image to the LLM or use a tunnel.
        # Many Vision APIs (OfferAI, Gemini) require a public URL or Base64.
        image_url = image_url_raw
    else:
        # Local path
        path_part = image_url_raw if image_url_raw.startswith("/") else f"/{image_url_raw}"
        image_url = f"{base_url}{path_part}"

    # CRITICAL FIX: If image_url is localhost, external LLMs (OpenAI/Gemini/Claude) CANNOT access it.
    # We must convert to Base64 if it's a local file.
    if "localhost" in image_url or "127.0.0.1" in image_url:
         import base64
         # Try to find the local file path from the URL
         # URL: http://localhost:8000/uploads/1/gen_xxx.png
         # File: backend/data/uploads/1/gen_xxx.png OR backend/uploads/...
         
         # 1. Parse relative path
         try:
             # removing http://localhost:8000/
             relative_path = image_url.replace(base_url, "")
             if relative_path.startswith("/"): relative_path = relative_path[1:]
             
             # 2. Heuristic search for file
             # We mounted /uploads map to settings.UPLOAD_DIR
             # But asset.url might include 'uploads/' prefix or might not depending on how it was saved.
             # Typically asset.url = "/uploads/filename.png"
             
             # If exact match fails, try prepending upload dir
             possible_paths = [
                 os.path.join(settings.UPLOAD_DIR, relative_path.replace("uploads/", "", 1)), # strip 'uploads/' prefix if dir is 'uploads'
                 os.path.join(settings.BASE_DIR, relative_path),
                 relative_path
             ]
             
             local_file_path = None
             for p in possible_paths:
                 if os.path.exists(p):
                     local_file_path = p
                     break
            
             if local_file_path:
                 logger.info(f"Localhost URL detected. Converting local file {local_file_path} to Base64 for remote LLM.")
                 def _read_and_encode():
                     with open(local_file_path, "rb") as image_file:
                         encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                     ext = os.path.splitext(local_file_path)[1].lower().replace(".", "")
                     mime = "image/png" if ext == "png" else "image/jpeg"
                     return f"data:{mime};base64,{encoded_string}"
                 image_url = await asyncio.to_thread(_read_and_encode)
             else:
                 logger.warning(f"Could not find local file for {image_url} to convert to Base64. Remote LLM might fail to fetch.")

         except Exception as e:
             logger.error(f"Failed to convert localhost image to base64: {e}")

    logger.info(f"Analyzing Image: {image_url[:100]}...") # Log truncate
    logger.info(f"Using LLM Config: Model={llm_config.get('model')}, BaseURL={llm_config.get('base_url')}")


    # 5. Call Service
    try:
        if billing_service.is_token_pricing(db, "analysis", api_provider, api_model):
            # Estimate based on the actual text prompt + conservative image token budget.
            # OpenAI vision format uses user message with [text, image_url].
            est_messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]
            est = billing_service.estimate_reserve_tokens_from_messages(est_messages)
            estimated_image_tokens = 1000
            est_input = int(est.get("input_tokens", 0) or 0) + estimated_image_tokens
            est_output = int(math.ceil(float(est_input) * billing_service.RESERVE_OUTPUT_RATIO)) if est_input > 0 else 0

            reserve_details = {
                "item": "asset_analysis",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "estimated_image_tokens": estimated_image_tokens,
                "input_tokens": est_input,
                "output_tokens": est_output,
                "total_tokens": int(est_input + est_output),
            }
            reservation_tx = billing_service.reserve_credits(
                db,
                current_user.id,
                "analysis",
                api_provider,
                api_model,
                reserve_details,
            )

        _release_db_connection(db, "analyze_asset_image_llm_call")

        response_data = await llm_service.analyze_multimodal(
            prompt=system_prompt,
            image_url=image_url,
            config=llm_config
        )
        
        result = response_data.get("content", "")
        usage = response_data.get("usage", {})
        
        billing_details = _build_standard_billing_details(
            item="asset_analysis",
            usage_payload=usage,
            extra_details={"request_scope": "analyze_asset_image"},
            routing_payload=response_data,
        )

        # HEURISTIC: Ensure image tokens are accounted for if usage seems low or missing
        # Standard GPT-4o high res is ~1000 tokens.
        # If input_tokens < 100, we likely didn't count the image.
        current_input = billing_details.get("prompt_tokens", billing_details.get("input_tokens", 0))
        if current_input < 200: 
            # Add estimated image tokens (e.g. 1000 per image)
            estimated_image_tokens = 1000
            
            # Update both keys for compatibility
            billing_details["input_tokens"] = current_input + estimated_image_tokens
            billing_details["prompt_tokens"] = billing_details["input_tokens"]
            
            if "total_tokens" in billing_details:
                billing_details["total_tokens"] += estimated_image_tokens
            else:
                billing_details["total_tokens"] = billing_details["input_tokens"] + billing_details.get("output_tokens", 0)

        _finalize_model_invocation_billing(
            db=db,
            current_user=current_user,
            task_type="analysis",
            provider=api_provider,
            model=api_model,
            reservation_tx=reservation_tx,
            item="asset_analysis",
            usage_payload=usage if isinstance(usage, dict) else None,
            extra_details=billing_details,
            routing_payload=response_data,
        )
        
        # 6. Save Result (Optional)
        # We don't have a specific field on Asset to store analysis unless we add one or use remark/meta.
        # However, for now we just return it.
        # If this is "analyze_script" or similar, we might save.
        # For "Asset Analysis", usually the user wants to see it or save it to asset meta.
        
        # Save to Asset Meta (Analysis Result)? 
        # Requirement: "Analyzes an asset...". User might expect persistence.
        # We'll save a snippet to 'remark' or 'meta_info.analysis'
        if asset is not None:
            asset = db.merge(asset)
            if not asset.meta_info:
                asset.meta_info = {}
            if isinstance(asset.meta_info, dict):
                meta = dict(asset.meta_info)
                meta["analysis_result"] = result
                asset.meta_info = meta
                db.commit()

        return {"result": result}
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        _cancel_reservation_quietly(db, locals().get("reservation_tx"), str(e))
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import BackgroundTasks



