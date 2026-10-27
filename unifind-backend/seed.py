"""Fill the database with the sample items from the frontend + an admin user.

Run once:  python seed.py
"""
import os
from datetime import date

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Item, ItemImage, User
from app.security import hash_password

SAMPLE = [
    ("Lost", "iPhone 13 (Black)", "Electronics", "Smartphone", "Colombo", "University of Colombo", "2026-10-01", "Black", "Apple", "Black iPhone 13 with a clear protective case. A small scratch is visible near the camera.", "photo-1592750475338-74b7b21085ab"),
    ("Found", "Student ID Card", "Documents & Cards", "Student ID", "Kalutara", "University of Kelaniya", "2026-09-28", "White", "University ID", "A student identity card was found near the library entrance. The name is hidden for privacy.", "photo-1606761568499-6d2451b23c66"),
    ("Lost", "Black Backpack", "Bags", "Backpack", "Kandy", "Kandy", "2026-09-25", "Black", "HP", "Black backpack with a laptop compartment, small keychain and a round logo patch.", "photo-1553062407-98eeb64c6a62"),
    ("Found", "Key Set", "Keys", "Key Set", "Galle", "Galle town", "2026-09-24", "Gold", "Unknown", "A small set of keys on a metal key ring was found near a bus stop.", "photo-1582139329536-e7284fece509"),
    ("Lost", "Samsung Earbuds", "Electronics", "Earbuds/Headphones", "Matara", "Matara", "2026-09-22", "Black", "Samsung", "Black wireless earbuds in a compact charging case.", "photo-1606220945770-b5b6c2c55bf1"),
    ("Found", "Wallet (Brown)", "Bags", "Wallet", "Kandy", "Kandy", "2026-09-20", "Brown", "Unknown", "A brown leather wallet was handed to the campus security office. Private contents are not shown.", "photo-1627123424574-724758594e93"),
]


def main():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        email = os.getenv("ADMIN_EMAIL", "admin@unifind.lk")
        password = os.getenv("ADMIN_PASSWORD", "ChangeMe12345")
        admin = db.scalar(select(User).where(User.email == email))
        if not admin:
            admin = User(full_name="Admin", email=email, password_hash=hash_password(password), role="admin")
            db.add(admin)
            db.flush()
            print(f"Created admin: {email} / {password}  (change this password!)")

        if not db.scalar(select(Item).limit(1)):
            for t, title, cat, sub, dist, loc, d, color, brand, desc, photo in SAMPLE:
                item = Item(
                    type=t, title=title, category=cat, subcategory=sub, district=dist,
                    location=loc, date=date.fromisoformat(d), color=color, brand=brand,
                    description=desc, owner_id=admin.id,
                )
                item.images.append(
                    ItemImage(path=f"https://images.unsplash.com/{photo}?auto=format&fit=crop&w=800&q=85")
                )
                db.add(item)
            print(f"Added {len(SAMPLE)} sample items")

        db.commit()


if __name__ == "__main__":
    main()
