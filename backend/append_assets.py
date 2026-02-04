
import os

path = r'c:\storyboard\AIStory\backend\app\api\endpoints.py'
try:
    with open(path, 'a', encoding='utf-8') as f:
        f.write("""

# --- Assets ---

class AssetCreate(BaseModel):
    url: str
    type: str # image, video
    meta_info: Optional[dict] = {}
    remark: Optional[str] = None

class AssetUpdate(BaseModel):
    remark: Optional[str] = None
    meta_info: Optional[dict] = None

@router.get("/assets/", response_model=List[dict])
def get_assets(
    type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Asset).filter(Asset.user_id == current_user.id)
    if type:
        query = query.filter(Asset.type == type)
    
    assets = query.all()
    # Simple serialization here, ideally use Pydantic schema
    return [
        {
            "id": a.id,
            "type": a.type,
            "url": a.url,
            "filename": a.filename,
            "meta_info": a.meta_info,
            "remark": a.remark,
            "created_at": a.created_at
        } for a in assets
    ]

@router.post("/assets/", response_model=dict)
def create_asset_url(
    asset_in: AssetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = Asset(
        user_id=current_user.id,
        type=asset_in.type,
        url=asset_in.url,
        meta_info=asset_in.meta_info,
        remark=asset_in.remark
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {
        "id": asset.id,
        "type": asset.type,
        "url": asset.url,
        "meta_info": asset.meta_info,
        "remark": asset.remark,
        "created_at": asset.created_at
    }

@router.post("/assets/upload", response_model=dict)
async def upload_asset(
    file: UploadFile = File(...),
    type: str = "image", # image or video
    remark: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Ensure upload directory
    upload_dir = settings.UPLOAD_DIR
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Construct URL (assuming /uploads is mounted)
    # Get base URL from request ideally, but relative works for frontend
    url = f"/uploads/{filename}"
    
    asset = Asset(
        user_id=current_user.id,
        type=type,
        url=url,
        filename=file.filename,
        meta_info={}, # Could add dimension extraction here
        remark=remark
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return {
        "id": asset.id,
        "type": asset.type,
        "url": asset.url,
        "filename": asset.filename,
        "meta_info": asset.meta_info,
        "remark": asset.remark,
        "created_at": asset.created_at
    }

@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.user_id == current_user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
        
    # Optional: Delete file if local
    # if asset.url.startswith("/uploads/"):
    #     ...
        
    db.delete(asset)
    db.commit()
    return {"status": "success"}

@router.put("/assets/{asset_id}", response_model=dict)
def update_asset(
    asset_id: int,
    asset_update: AssetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.user_id == current_user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    if asset_update.remark is not None:
        asset.remark = asset_update.remark
    if asset_update.meta_info is not None:
         # Merge or replace? Let's replace for now or merge if needed
         # asset.meta_info = {**asset.meta_info, **asset_update.meta_info} 
         asset.meta_info = asset_update.meta_info
         
    db.commit()
    db.refresh(asset)
    
    return {
        "id": asset.id,
        "type": asset.type,
        "url": asset.url,
        "meta_info": asset.meta_info,
        "remark": asset.remark,
        "created_at": asset.created_at
    }
""")
    print("Success")
except Exception as e:
    print(e)
