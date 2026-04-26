from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.all_models import User, UserGroup, UserGroupMembership, ProjectGroupCreditAllocation, Project
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/groups", tags=["groups"])

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    
class GroupMemberAdd(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    permission_level: int = 1

class GroupAllocation(BaseModel):
    group_id: int
    credit_limit: int

@router.post("/", response_model=dict)
def create_group(
    group_in: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_group = UserGroup(
        name=group_in.name,
        description=group_in.description,
        owner_id=current_user.id
    )
    db.add(new_group)
    db.flush() # to get id
    
    membership = UserGroupMembership(
        user_id=current_user.id,
        group_id=new_group.id,
        permission_level=2 # Owner
    )
    db.add(membership)
    current_user.current_group_id = new_group.id
    
    # Actually update DB user
    real_user = db.query(User).filter(User.id == current_user.id).first()
    if real_user:
        real_user.current_group_id = new_group.id
    db.commit()
    db.refresh(new_group)
    
    return {"id": new_group.id, "name": new_group.name}

@router.get("/me", response_model=List[dict])
def get_my_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    memberships = db.query(UserGroupMembership).filter(UserGroupMembership.user_id == current_user.id).all()
    results = []
    for m in memberships:
        if m.group:
            results.append({
                "group_id": m.group.id,
                "name": m.group.name,
                "permission_level": m.permission_level,
                "is_current": (getattr(current_user, "current_group_id", None) == m.group.id),
                "credits": m.group.credits or 0
            })
    return results

@router.post("/{group_id}/members", response_model=dict)
def add_member(
    group_id: int,
    member_in: GroupMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    membership = db.query(UserGroupMembership).filter(
        UserGroupMembership.group_id == group_id,
        UserGroupMembership.user_id == current_user.id,
        UserGroupMembership.permission_level >= 2
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Not authorized to add members to this group.")
        
    target_user = None
    if member_in.user_id:
        target_user = db.query(User).filter(User.id == member_in.user_id).first()
    elif member_in.username:
        target_user = db.query(User).filter(User.username == member_in.username).first()
    elif member_in.email:
        target_user = db.query(User).filter(User.email == member_in.email).first()
        
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
        
    existing = db.query(UserGroupMembership).filter(
        UserGroupMembership.group_id == group_id,
        UserGroupMembership.user_id == target_user.id
    ).first()
    
    if existing:
         raise HTTPException(status_code=400, detail="User already in group.")
         
    new_membership = UserGroupMembership(
        user_id=target_user.id,
        group_id=group_id,
        permission_level=member_in.permission_level
    )
    db.add(new_membership)
    db.commit()
    return {"message": "Success"}

@router.post("/projects/{project_id}/allocations", response_model=dict)
def set_project_allocation(
    project_id: int,
    alloc_in: GroupAllocation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Ensure project exists and user has access
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == current_user.id).first()
    if not project:
         raise HTTPException(status_code=404, detail="Project not found or not owned by user.")
         
    membership = db.query(UserGroupMembership).filter(
        UserGroupMembership.group_id == alloc_in.group_id,
        UserGroupMembership.user_id == current_user.id,
        UserGroupMembership.permission_level >= 2
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not authorized to manage this group.")
        
    allocation = db.query(ProjectGroupCreditAllocation).filter(
         ProjectGroupCreditAllocation.project_id == project_id,
         ProjectGroupCreditAllocation.group_id == alloc_in.group_id
    ).first()
    
    if allocation:
        allocation.credit_limit = alloc_in.credit_limit
    else:
        new_alloc = ProjectGroupCreditAllocation(
            project_id=project_id,
            group_id=alloc_in.group_id,
            user_id=current_user.id,
            granted_by=current_user.id,
            credit_limit=alloc_in.credit_limit
        )
        db.add(new_alloc)
        
    db.commit()
    return {"message": "Success"}
