from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Item, SavedItem, User
from ..schemas import ItemOut
from ..security import get_current_user
from ..serializers import item_to_dict

router = APIRouter(prefix="/saved", tags=["saved"])


@router.get("", response_model=list[ItemOut])
def list_saved(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Item)
        .join(SavedItem, SavedItem.item_id == Item.id)
        .where(SavedItem.user_id == user.id)
        .order_by(SavedItem.id.desc())
    ).all()
    return [item_to_dict(i) for i in rows]


@router.put("/{item_id}", status_code=204)
def save_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.get(Item, item_id):
        raise HTTPException(404, "Item not found")
    exists = db.scalar(
        select(SavedItem).where(SavedItem.user_id == user.id, SavedItem.item_id == item_id)
    )
    if not exists:
        db.add(SavedItem(user_id=user.id, item_id=item_id))
        db.commit()


@router.delete("/{item_id}", status_code=204)
def unsave_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(
        select(SavedItem).where(SavedItem.user_id == user.id, SavedItem.item_id == item_id)
    )
    if row:
        db.delete(row)
        db.commit()
