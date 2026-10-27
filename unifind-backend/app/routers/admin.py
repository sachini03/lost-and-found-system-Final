from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Item, User
from ..security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    def count(*conds):
        return db.scalar(select(func.count()).select_from(Item).where(*conds)) or 0

    return {
        "total_items": count(),
        "lost": count(Item.type == "Lost"),
        "found": count(Item.type == "Found"),
        "resolved": count(Item.status == "Resolved"),
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
    }
