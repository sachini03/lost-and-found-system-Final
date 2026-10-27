from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Message, Notification, User
from ..security import get_current_user
from .conversations import iso

router = APIRouter(prefix="/notifications", tags=["notifications"])


def to_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "conversation_id": n.conversation_id,
        "item_id": n.item_id,
        "is_read": n.is_read,
        "created_at": iso(n.created_at),
    }


@router.get("")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(100)
    ).all()
    return [to_dict(n) for n in rows]


@router.get("/summary")
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Tiny response the frontend polls to drive the bell + message badges."""
    unread_notifications = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
    ) or 0
    unread_messages = db.scalar(
        select(func.count())
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            (Conversation.owner_id == user.id) | (Conversation.starter_id == user.id),
            Message.sender_id != user.id,
            Message.read_at.is_(None),
        )
    ) or 0
    return {"unread_notifications": unread_notifications, "unread_messages": unread_messages}


@router.post("/read-all", status_code=204)
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()


@router.post("/{notification_id}/read", status_code=204)
def read_one(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    n.is_read = True
    db.commit()
