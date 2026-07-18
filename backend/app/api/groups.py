from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session, joinedload
from app.api.deps import get_current_user
from app.core.time_utils import now_bj_iso
from app.db.session import get_db, engine
from app.db.init_db import check_and_migrate_tables, _ensure_user_group_schema
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
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/groups", tags=["groups"])


def _is_schema_compat_error(exc: Exception) -> bool:
    raw = str(getattr(exc, "orig", exc) or exc).strip().lower()
    if not raw:
        return False
    markers = (
        "undefinedcolumn",
        "undefinedtable",
        "does not exist",
        "no such column",
        "no such table",
        "relation",
    )
    return any(marker in raw for marker in markers)


def _run_with_schema_self_heal(db: Session, operation, *, context: str):
    try:
        return operation()
    except (OperationalError, ProgrammingError) as exc:
        if not _is_schema_compat_error(exc):
            raise
        logger.warning("[%s] detected schema mismatch, ensuring user-group schema and retrying once: %s", context, exc)
        try:
            db.rollback()
        except Exception:
            pass
        is_postgres = getattr(engine.dialect, "name", "") == "postgresql"
        _ensure_user_group_schema(is_postgres=is_postgres)
        check_and_migrate_tables()
        return operation()

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    credits: Optional[int] = None
    owner_id: Optional[int] = None
    allow_group_credit_billing: Optional[bool] = None

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


class GroupCreditAllocateItem(BaseModel):
    user_id: int
    amount: int


class GroupCreditAllocate(BaseModel):
    """Distribute group pool credits into members' personal balances.

    mode:
      - equal: split total_amount (or full pool) across user_ids (or all members)
      - custom: use allocations list as-is (manual amounts)
    After equal preview on the client, callers typically submit mode=custom with edited amounts.
    """
    mode: str = "custom"  # equal | custom
    total_amount: Optional[int] = None
    user_ids: Optional[List[int]] = None
    allocations: Optional[List[GroupCreditAllocateItem]] = None


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
        "allow_group_credit_billing": bool(getattr(group, "allow_group_credit_billing", False)),
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
        "personal_credits": int(user.credits or 0) if user else 0,
        "created_at": m.created_at,
    }


def _build_equal_allocations(user_ids: List[int], total_amount: int) -> List[dict]:
    """Split total_amount across user_ids; remainder +1 to first recipients."""
    n = len(user_ids)
    if n <= 0 or total_amount <= 0:
        return []
    base = total_amount // n
    rem = total_amount % n
    out = []
    for i, uid in enumerate(user_ids):
        amt = base + (1 if i < rem else 0)
        if amt > 0:
            out.append({"user_id": int(uid), "amount": int(amt)})
    return out


@router.get("/schema-status", response_model=dict)
def get_group_schema_status(
    current_user: User = Depends(get_current_user),
):
    _require_superuser(current_user)
    from app.db.init_db import inspect_user_group_schema
    snapshot = inspect_user_group_schema()
    required_tables = (
        "user_groups",
        "user_group_memberships",
        "project_group_credit_allocations",
    )
    missing_tables = [name for name in required_tables if not snapshot["tables"].get(name)]
    required_columns = {
        "users": ["current_group_id"],
        "user_groups": ["id", "name", "credits", "owner_id"],
        "user_group_memberships": ["user_id", "group_id", "permission_level"],
    }
    missing_columns = {}
    for table_name, cols in required_columns.items():
        existing = set(snapshot["columns"].get(table_name) or [])
        absent = [c for c in cols if c not in existing]
        if absent:
            missing_columns[table_name] = absent
    return {
        "ok": not missing_tables and not missing_columns,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "snapshot": snapshot,
    }


@router.post("/", response_model=dict)
def create_group(
    group_in: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    def _persist():
        new_group = UserGroup(
            name=group_in.name,
            description=group_in.description,
            owner_id=current_user.id,
            allow_group_credit_billing=False,
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

    return _run_with_schema_self_heal(db, _persist, context="create_group")


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
                "allow_group_credit_billing": bool(getattr(m.group, "allow_group_credit_billing", False)),
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

    if group_in.allow_group_credit_billing is not None:
        group.allow_group_credit_billing = bool(group_in.allow_group_credit_billing)

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


@router.post("/{group_id}/credits/allocate", response_model=dict)
def allocate_group_credits(
    group_id: int,
    body: GroupCreditAllocate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transfer credits from the group shared pool to members' personal balances."""
    _require_group_admin_or_superuser(db, group_id, current_user)

    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    memberships = (
        db.query(UserGroupMembership)
        .options(joinedload(UserGroupMembership.user))
        .filter(UserGroupMembership.group_id == group_id)
        .all()
    )
    member_by_id = {m.user_id: m for m in memberships}
    if not member_by_id:
        raise HTTPException(status_code=400, detail="Group has no members")

    mode = (body.mode or "custom").strip().lower()
    pool = int(group.credits or 0)

    if mode == "equal":
        if body.user_ids:
            target_ids = [int(uid) for uid in body.user_ids]
        else:
            target_ids = list(member_by_id.keys())
        for uid in target_ids:
            if uid not in member_by_id:
                raise HTTPException(status_code=400, detail=f"User {uid} is not a member of this group")
        if body.total_amount is None:
            total = pool
        else:
            total = int(body.total_amount)
        if total <= 0:
            raise HTTPException(status_code=400, detail="total_amount must be positive")
        if total > pool:
            raise HTTPException(status_code=400, detail="Insufficient group credits")
        plan = _build_equal_allocations(target_ids, total)
    elif mode == "custom":
        if not body.allocations:
            raise HTTPException(status_code=400, detail="allocations required for custom mode")
        plan = []
        for item in body.allocations:
            amt = int(item.amount)
            if amt < 0:
                raise HTTPException(status_code=400, detail="Allocation amount cannot be negative")
            if amt == 0:
                continue
            plan.append({"user_id": int(item.user_id), "amount": amt})
        if not plan:
            raise HTTPException(status_code=400, detail="No positive allocations provided")
    else:
        raise HTTPException(status_code=400, detail="Invalid mode. Use equal or custom.")

    # Merge duplicate user_ids
    merged: dict = {}
    for row in plan:
        uid = int(row["user_id"])
        merged[uid] = merged.get(uid, 0) + int(row["amount"])
    plan = [{"user_id": uid, "amount": amt} for uid, amt in merged.items() if amt > 0]

    for row in plan:
        if row["user_id"] not in member_by_id:
            raise HTTPException(
                status_code=400,
                detail=f"User {row['user_id']} is not a member of this group",
            )

    total_out = sum(row["amount"] for row in plan)
    if total_out <= 0:
        raise HTTPException(status_code=400, detail="Total allocation must be positive")
    if total_out > pool:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient group credits: need {total_out}, have {pool}",
        )

    group.credits = pool - total_out
    group.updated_at = now_bj_iso()

    results = []
    for row in plan:
        uid = row["user_id"]
        amt = row["amount"]
        user = member_by_id[uid].user
        if not user:
            user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User {uid} not found")
        old_personal = int(user.credits or 0)
        user.credits = old_personal + amt
        db.add(TransactionHistory(
            user_id=uid,
            target_group_id=group_id,
            amount=amt,
            balance_after=int(user.credits or 0),
            description="group_credit_allocate",
            details={
                "task_type": "group_credit_allocate",
                "operator_id": current_user.id,
                "group_id": group_id,
                "mode": mode,
                "from_group_credits": True,
                "personal_before": old_personal,
            },
        ))
        results.append({
            "user_id": uid,
            "username": user.username,
            "amount": amt,
            "personal_credits": int(user.credits or 0),
        })

    db.add(TransactionHistory(
        user_id=current_user.id,
        target_group_id=group_id,
        amount=-total_out,
        balance_after=int(group.credits or 0),
        description="group_credit_allocate_pool",
        details={
            "task_type": "group_credit_allocate_pool",
            "operator_id": current_user.id,
            "group_id": group_id,
            "mode": mode,
            "total_allocated": total_out,
            "recipients": [{"user_id": r["user_id"], "amount": r["amount"]} for r in results],
        },
    ))
    db.commit()
    db.refresh(group)

    return {
        "group_id": group_id,
        "mode": mode,
        "total_allocated": total_out,
        "group_credits": int(group.credits or 0),
        "allocations": results,
    }


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
    def _persist():
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

    return _run_with_schema_self_heal(db, _persist, context="add_group_member")


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
