import secrets

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import MAX_FILES_PER_REQUEST, MAX_UPLOAD_BYTES, UPLOAD_DIR
from ..database import get_db
from ..models import Item, ItemImage, Notification, User
from ..schemas import ItemCreate, ItemOut, StatusUpdate
from ..security import get_current_user
from ..serializers import item_to_dict
from ..storage import upload_photo, delete_photo

router = APIRouter(prefix="/items", tags=["items"])

def sniff_image(data: bytes) -> str | None:
    """Return a file extension if the bytes really are PNG/JPEG/WEBP."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def get_item_or_404(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


@router.get("", response_model=list[ItemOut])
def list_items(
    q: str | None = None,
    type: str | None = Query(default=None, pattern="^(Lost|Found)$"),
    category: str | None = None,
    district: str | None = None,
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Item).where(Item.status == "Active")
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Item.title.ilike(like),
                Item.description.ilike(like),
                Item.category.ilike(like),
                Item.subcategory.ilike(like),
                Item.district.ilike(like),
                Item.location.ilike(like),
            )
        )
    if type:
        stmt = stmt.where(Item.type == type)
    if category:
        stmt = stmt.where(Item.category == category)
    if district:
        stmt = stmt.where(Item.district == district)
    order = (Item.date.desc(), Item.id.desc()) if sort == "newest" else (Item.date.asc(), Item.id.asc())
    stmt = stmt.order_by(*order).limit(limit).offset(offset)
    return [item_to_dict(i) for i in db.scalars(stmt).all()]


@router.get("/mine", response_model=list[ItemOut])
def my_items(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Item).where(Item.owner_id == user.id).order_by(Item.id.desc())
    ).all()
    return [item_to_dict(i) for i in rows]


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    return item_to_dict(get_item_or_404(db, item_id))


@router.post("", response_model=ItemOut, status_code=201)
def create_item(
    data: ItemCreate,
    user: User = Depends(get_current_user),  # login required -> owner_id is always set
    db: Session = Depends(get_db),
):
    item = Item(**data.model_dump(), owner_id=user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item_to_dict(item)


@router.post("/{item_id}/images", response_model=ItemOut)
async def upload_images(
    item_id: int,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = get_item_or_404(db, item_id)

    # Only the reporter (or an admin) may add photos
    if item.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your report")

    if len(files) > MAX_FILES_PER_REQUEST or len(item.images) + len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Maximum {MAX_FILES_PER_REQUEST} photos per report",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    for file in files:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"{file.filename}: file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            )
        ext = sniff_image(data)
        if ext is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{file.filename}: only PNG, JPG or WEBP images are allowed",
            )
        name = f"{secrets.token_hex(16)}{ext}"  # never trust the client filename
        (UPLOAD_DIR / name).write_bytes(data)
        saved_paths.append(f"/uploads/{name}")

    for path in saved_paths:
        db.add(ItemImage(item_id=item.id, path=path))
    db.commit()
    db.refresh(item)
    return item_to_dict(item)


@router.patch("/{item_id}/status", response_model=ItemOut)
def update_status(
    item_id: int,
    data: StatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = get_item_or_404(db, item_id)
    if item.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your report")
    was_active = item.status == "Active"
    item.status = data.status
    # Tell everyone who was chatting about this report that it is closed.
    if data.status == "Resolved" and was_active:
        for conv in item.conversations:
            other_id = conv.starter_id if user.id == conv.owner_id else conv.owner_id
            if other_id == user.id:
                continue
            db.add(
                Notification(
                    user_id=other_id, type="resolved", conversation_id=conv.id, item_id=item.id,
                    title=f"“{item.title}” was marked as resolved",
                    body="The reporter closed this report. Thanks for helping!",
                )
            )
    db.commit()
    db.refresh(item)
    return item_to_dict(item)


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = get_item_or_404(db, item_id)
    if item.owner_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your report")
    for img in item.images:
        if img.path.startswith("/uploads/"):
            (UPLOAD_DIR / img.path.removeprefix("/uploads/")).unlink(missing_ok=True)
    db.delete(item)
    db.commit()
