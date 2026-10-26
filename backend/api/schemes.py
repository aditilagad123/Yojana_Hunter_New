from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from database import SessionLocal
from models import Scheme

router = APIRouter()

@router.get("/")
async def list_schemes(
    q: Optional[str] = Query(None, description="Search keyword"),
    state: Optional[str] = Query(None, description="State filter"),
    category: Optional[str] = Query(None, description="Beneficiary category"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(12, ge=1, le=100, description="Items per page")
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        query = db.query(Scheme).filter(
            Scheme.is_active == True,
            Scheme.status == "published",
            Scheme.admin_review_status.in_(["approved", "published"]),
            (Scheme.is_test == False) | (Scheme.is_test.is_(None))
        )
        if category and category.lower() != "all":
            query = query.filter(Scheme.category.ilike(f"%{category}%"))
        if state and state.lower() != "all":
            query = query.filter(
                (Scheme.state.ilike(f"%{state}%")) | (Scheme.state.ilike("%all india%"))
            )
        if q:
            q_clean = q.lower().strip()
            query = query.filter(
                (Scheme.name.ilike(f"%{q_clean}%")) |
                (Scheme.short_description.ilike(f"%{q_clean}%")) |
                (Scheme.department.ilike(f"%{q_clean}%")) |
                (Scheme.benefits.ilike(f"%{q_clean}%"))
            )
        total = query.count()
        records = query.offset((page - 1) * page_size).limit(page_size).all()
        schemes = [s.to_dict(include_rules=True) for s in records]
        return {
            "schemes": schemes,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    finally:
        db.close()

@router.get("/{scheme_id}")
async def get_scheme_detail(scheme_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        scheme = None
        if scheme_id.isdigit():
            scheme = db.query(Scheme).filter(Scheme.id == int(scheme_id)).first()
        if not scheme:
            scheme = db.query(Scheme).filter(Scheme.slug == scheme_id).first()
        if not scheme:
            raise HTTPException(status_code=404, detail="Scheme not found")
        return scheme.to_dict(include_rules=True)
    finally:
        db.close()
