"""Chat between the person who reported an item and anyone who contacts them.

Flow
  1. Someone opens a report and clicks "Message reporter"   -> POST /conversations
  2. They exchange messages                                  -> POST /conversations/{id}/messages
  3. Each new message creates / refreshes a notification for the other person
  4. The other person's client polls GET .../messages?after_id=N and sees it
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Item, Message, Notification, User, utcnow
from ..schemas import ConversationCreate, MessageCreate
from ..security import get_current_user
from ..serializers import PLACEHOLDER

router = APIRouter(prefix="/conversations", tags=["chat"])


# ---------------- helpers ----------------
def iso(dt: datetime | None) -> str | None:
    """Timestamps are stored as naive UTC; send them with a 'Z' so browsers convert correctly."""
    return dt.isoformat() + "Z" if dt else None


def first_name(user: User) -> str:
    return (user.full_name.split() or ["User"])[0]


def message_to_dict(m: Message) -> dict:
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "sender_id": m.sender_id,
        "body": m.body,
        "created_at": iso(m.created_at),
    }


def conversation_to_dict(conv: Conversation, me: User, db: Session) -> dict:
    other = conv.starter if me.id == conv.owner_id else conv.owner
    item = conv.item
    last = db.scalar(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.desc()).limit(1)
    )
    unread = db.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conv.id,
            Message.sender_id != me.id,
            Message.read_at.is_(None),
        )
    ) or 0
    return {
        "id": conv.id,
        "item": {
            "id": item.id,
            "title": item.title,
            "type": item.type,
            "status": item.status,
            "date": item.date,
            "district": item.district,
            "image": item.images[0].path if item.images else PLACEHOLDER,
            "owner_id": item.owner_id,
        },
        "i_am_item_owner": me.id == conv.owner_id,
        # Only the first name is shared. E-mail and phone never leave the server.
        "other_name": first_name(other),
        "last_message": message_to_dict(last) if last else None,
        "unread_count": unread,
        "updated_at": iso(conv.updated_at),
    }


def get_my_conversation(db: Session, conv_id: int, user: User) -> Conversation:
    conv = db.get(Conversation, conv_id)
    # 404 (not 403) so strangers cannot even tell that a chat exists
    if not conv or user.id not in (conv.owner_id, conv.starter_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv


def notify_new_message(db: Session, conv: Conversation, sender: User, text: str) -> None:
    """One unread notification per chat: new messages refresh it instead of piling up."""
    recipient_id = conv.owner_id if sender.id == conv.starter_id else conv.starter_id
    title = f"New message about “{conv.item.title}”"
    preview = text if len(text) <= 90 else text[:87] + "..."
    body = f"{first_name(sender)}: {preview}"

    existing = db.scalar(
        select(Notification).where(
            Notification.user_id == recipient_id,
            Notification.conversation_id == conv.id,
            Notification.type == "message",
            Notification.is_read.is_(False),
        )
    )
    if existing:
        existing.title, existing.body, existing.created_at = title, body, utcnow()
    else:
        db.add(
            Notification(
                user_id=recipient_id, type="message", title=title, body=body,
                conversation_id=conv.id, item_id=conv.item_id,
            )
        )


# ---------------- endpoints ----------------
@router.post("")
def start_conversation(
    data: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Open (or re-open) the chat between me and the reporter of an item."""
    item = db.get(Item, data.item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    if item.owner_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This report has no registered owner to message")
    if item.owner_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This is your own report")

    conv = db.scalar(
        select(Conversation).where(
            Conversation.item_id == item.id, Conversation.starter_id == user.id
        )
    )
    if not conv:
        if item.status != "Active":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "This report is already resolved")
        conv = Conversation(item_id=item.id, owner_id=item.owner_id, starter_id=user.id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conversation_to_dict(conv, user, db)


@router.get("")
def my_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    has_messages = select(Message.id).where(Message.conversation_id == Conversation.id).exists()
    rows = db.scalars(
        select(Conversation)
        .where(
            or_(Conversation.owner_id == user.id, Conversation.starter_id == user.id),
            # the reporter only sees a chat once the other person has actually written
            or_(Conversation.starter_id == user.id, has_messages),
        )
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    ).all()
    return [conversation_to_dict(c, user, db) for c in rows]


@router.get("/{conv_id}")
def get_conversation(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return conversation_to_dict(get_my_conversation(db, conv_id, user), user, db)


@router.get("/{conv_id}/messages")
def list_messages(
    conv_id: int,
    after_id: int = Query(default=0, ge=0, description="only messages newer than this id (for polling)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = get_my_conversation(db, conv_id, user)
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id, Message.id > after_id)
        .order_by(Message.id)
        .limit(500)
    ).all()

    # opening the chat = reading it: mark the other person's messages as read
    # and clear the matching "new message" notification
    now = utcnow()
    changed = False
    for m in rows:
        if m.sender_id != user.id and m.read_at is None:
            m.read_at = now
            changed = True
    for n in db.scalars(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.conversation_id == conv.id,
            Notification.type == "message",
            Notification.is_read.is_(False),
        )
    ):
        n.is_read = True
        changed = True
    if changed:
        db.commit()
    return [message_to_dict(m) for m in rows]


@router.post("/{conv_id}/messages", status_code=201)
def send_message(
    conv_id: int,
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = get_my_conversation(db, conv_id, user)
    msg = Message(conversation_id=conv.id, sender_id=user.id, body=data.body)
    db.add(msg)
    conv.updated_at = utcnow()
    notify_new_message(db, conv, user, data.body)
    db.commit()
    db.refresh(msg)
    return message_to_dict(msg)
