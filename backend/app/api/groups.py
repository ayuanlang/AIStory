from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_current_user
from app.core.time_utils import now_bj_iso
from app.db.session import get_db
from app.models.all_models import (
    User,
    UserGroup,
    UserGroupMembership,
    ProjectGroupCreditAllocation,
    Project,
    TransactionHistory,
    PaymentOrder,
    InvoiceProfile,
)
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/groups", tags=["groups"])

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    credits: Optional[int] = None
    owner_id: Optional[int] = None

class GroupCreditsUpdate(BaseModel):
    amount: int
    mode: str = "set"  # set | add

class GroupMemberAdd(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    permission_level: int = 1

class GroupMemberUpdate(BaseModel):
    permission_level: Optional[int] = None
    credit_share_limit: Optional[int] = None

class GroupAllocation(BaseModel):
    group_id: int
    credit_limit: int


def _require_superuser(user: User) -> None:
    if not getattr(user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _require_group_membership(db: Session, group_id: int, user_id: int) -> UserGroupMembership:
    membership = db.query(UserGroupMembership).filter(
        UserGroupMembership.group_id == group_id,
        UserGroupMembership.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this group.")
    return membership


def _require_group_admin_or_superuser(db: Session, group_id: int, user: User) -> None:
    if getattr(user, "is_superuser", False):
        return
    membership = db.query(UserGroupMembership).filter(
        UserGroupMembership.group_id == group_id,
        UserGroupMembership.user_id == user.id,
        UserGroupMembership.permission_level >= 2,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not authorized to manage this group.")


def _resolve_target_user(db: Session, member_in: GroupMemberAdd) -> User:
    target_user = None
    if member_in.user_id:
        target_user = db.query(User).filter(User.id == member_in.user_id).first()
    elif member_in.username:
        username = (member_in.username or "").strip()
        if "@" in username:
            target_user = db.query(User).filter(User.email == username.lower()).first()
        if not target_user:
            target_user = db.query(User).filter(User.username == username).first()
    elif member_in.email:
        target_user = db.query(User).filter(User.email == (member_in.email or "").strip().lower()).first()

    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    return target_user


def _serialize_group(group: UserGroup, member_count: int = 0) -> dict:
    owner = group.owner
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "credits": group.credits or 0,
        "owner_id": group.owner_id,
        "owner_username": owner.username if owner else None,
        "owner_email": owner.email if owner else None,
        "member_count": int(member_count or 0),
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


def _serialize_member(m: UserGroupMembership) -> dict:
    user = m.user
    return {
        "user_id": m.user_id,
        "username": user.username if user else None,
        "email": user.email if user else None,
        "full_name": user.full_name if user else None,
        "permission_level": m.permission_level,
        "credit_share_limit": m.credit_share_limit or 0,
        "created_at": m.created_at,
    }


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
    db.flush()  # to get id

    membership = UserGroupMembership(
        user_id=current_user.id,
        group_id=new_group.id,
        permission_level=2  # Owner
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


@router.get("/page", response_model=dict)
def get_groups_page(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_superuser(current_user)

    safe_page = max(int(page or 1), 1)
    safe_page_size = max(1, min(int(page_size or 20), 200))
    skip = (safe_page - 1) * safe_page_size

    total = int(db.query(UserGroup).count())
    groups = (
        db.query(UserGroup)
        .options(joinedload(UserGroup.owner))
        .order_by(UserGroup.id.asc())
        .offset(skip)
        .limit(safe_page_size)
        .all()
    )
    group_ids = [g.id for g in groups]
    member_counts = {}
    if group_ids:
        rows = (
            db.query(UserGroupMembership.group_id, func.count(UserGroupMembership.id))
            .filter(UserGroupMembership.group_id.in_(group_ids))
            .group_by(UserGroupMembership.group_id)
            .all()
        )
        member_counts = {gid: cnt for gid, cnt in rows}

    return {
        "items": [_serialize_group(g, member_counts.get(g.id, 0)) for g in groups],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
    }


@router.get("/me", response_model=List[dict])
def get_my_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    memberships = db.query(UserGroupMembership).filter(UserGroupMembership.user_id == current_user.id).all()
    group_ids = [m.group_id for m in memberships if m.group]
    member_counts = {}
    if group_ids:
        rows = (
            db.query(UserGroupMembership.group_id, func.count(UserGroupMembership.id))
            .filter(UserGroupMembership.group_id.in_(group_ids))
            .group_by(UserGroupMembership.group_id)
            .all()
        )
        member_counts = {gid: cnt for gid, cnt in rows}

    results = []
    for m in memberships:
        if m.group:
            results.append({
                "group_id": m.group.id,
                "name": m.group.name,
                "permission_level": m.permission_level,
                "is_current": (getattr(current_user, "current_group_id", None) == m.group.id),
                "credits": m.group.credits or 0,
                "member_count": member_counts.get(m.group.id, 0),
            })
    return results


@router.put("/{group_id}", response_model=dict)
def update_group(
    group_id: int,
    group_in: GroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_superuser(current_user)

    group = db.query(UserGroup).options(joinedload(UserGroup.owner)).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if group_in.name is not None:
        next_name = (group_in.name or "").strip()
        if not next_name:
            raise HTTPException(status_code=400, detail="Group name cannot be empty")
        group.name = next_name

    if group_in.description is not None:
        group.description = (group_in.description or "").strip() or None

    if group_in.credits is not None:
        group.credits = int(group_in.credits)

    if group_in.owner_id is not None:
        new_owner = db.query(User).filter(User.id == group_in.owner_id).first()
        if not new_owner:
            raise HTTPException(status_code=404, detail="Owner user not found")
        group.owner_id = new_owner.id
        owner_membership = db.query(UserGroupMembership).filter(
            UserGroupMembership.group_id == group_id,
            UserGroupMembership.user_id == new_owner.id,
        ).first()
        if owner_membership:
            owner_membership.permission_level = max(int(owner_membership.permission_level or 1), 2)
        else:
            db.add(UserGroupMembership(
                user_id=new_owner.id,
                group_id=group_id,
                permission_level=2,
            ))

    group.updated_at = now_bj_iso()
    db.commit()
    db.refresh(group)

    member_count = (
        db.query(func.count(UserGroupMembership.id))
        .filter(UserGroupMembership.group_id == group_id)
        .scalar()
    ) or 0
    return _serialize_group(group, member_count)


@router.post("/{group_id}/credits", response_model=dict)
def update_group_credits(
    group_id: int,
    credit_update: GroupCreditsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_superuser(current_user)

    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    old_credits = group.credits or 0
    if credit_update.mode == "add":
        group.credits = old_credits + int(credit_update.amount)
    else:
        group.credits = int(credit_update.amount)

    group.updated_at = now_bj_iso()
    db.add(TransactionHistory(
        user_id=current_user.id,
        target_group_id=group_id,
        amount=group.credits - old_credits,
        balance_after=group.credits,
        description="admin_group_adjustment",
        details={
            "task_type": "admin_group_adjustment",
            "admin_id": current_user.id,
            "reason": "Manual Group Update",
            "mode": credit_update.mode,
        },
    ))
    db.commit()
    return {"credits": group.credits}


@router.delete("/{group_id}", response_model=dict)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_superuser(current_user)

    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db.query(User).filter(User.current_group_id == group_id).update(
        {User.current_group_id: None},
        synchronize_session=False,
    )
    db.query(ProjectGroupCreditAllocation).filter(
        ProjectGroupCreditAllocation.group_id == group_id
    ).delete(synchronize_session=False)
    db.query(UserGroupMembership).filter(
        UserGroupMembership.group_id == group_id
    ).delete(synchronize_session=False)
    db.query(TransactionHistory).filter(
        TransactionHistory.target_group_id == group_id
    ).update(
        {TransactionHistory.target_group_id: None},
        synchronize_session=False,
    )
    db.query(PaymentOrder).filter(PaymentOrder.target_group_id == group_id).update(
        {PaymentOrder.target_group_id: None},
        synchronize_session=False,
    )
    db.query(InvoiceProfile).filter(InvoiceProfile.group_id == group_id).update(
        {InvoiceProfile.group_id: None},
        synchronize_session=False,
    )

    db.delete(group)
    db.commit()
    return {"message": "Success"}


@router.get("/{group_id}/members", response_model=List[dict])
def list_members(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not getattr(current_user, "is_superuser", False):
        _require_group_membership(db, group_id, current_user.id)

    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    memberships = (
        db.query(UserGroupMembership)
        .options(joinedload(UserGroupMembership.user))
        .filter(UserGroupMembership.group_id == group_id)
        .order_by(UserGroupMembership.permission_level.desc(), UserGroupMembership.id.asc())
        .all()
    )
    return [_serialize_member(m) for m in memberships]


@router.post("/{group_id}/members", response_model=dict)
def add_member(
    group_id: int,
    member_in: GroupMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_group_admin_or_superuser(db, group_id, current_user)

    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    target_user = _resolve_target_user(db, member_in)

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


@router.put("/{group_id}/members/{user_id}", response_model=dict)
def update_member(
    group_id: int,
    user_id: int,
    member_in: GroupMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_group_admin_or_superuser(db, group_id, current_user)

    membership = db.query(UserGroupMembership).options(
        joinedload(UserGroupMembership.user)
    ).filter(
        UserGroupMembership.group_id == group_id,
        UserGroupMembership.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")

    if member_in.permission_level is not None:
        level = int(member_in.permission_level)
        if level < 1:
            raise HTTPException(status_code=400, detail="Invalid permission level")
        membership.permission_level = level

    if member_in.credit_share_limit is not None:
        membership.credit_share_limit = max(0, int(member_in.credit_share_limit))

    db.commit()
    db.refresh(membership)
    return _serialize_member(membership)


@router.delete("/{group_id}/members/{user_id}", response_model=dict)
def remove_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_group_admin_or_superuser(db, group_id, current_user)

    membership = db.query(UserGroupMembership).filter(
        UserGroupMembership.group_id == group_id,
        UserGroupMembership.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")

    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if group and group.owner_id == user_id and not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=400, detail="Cannot remove group owner")

    user = db.query(User).filter(User.id == user_id).first()
    if user and getattr(user, "current_group_id", None) == group_id:
        user.current_group_id = None

    db.delete(membership)
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
    if not membership and not getattr(current_user, "is_superuser", False):
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
