import os, sys, tempfile
from datetime import date, timedelta

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = _tmp + "/uploads"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Item, User  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 50
GOOD = {
    "type": "Lost", "title": "Blue bottle", "category": "Personal Items",
    "subcategory": "Bottle", "district": "Colombo", "location": "Library",
    "date": date.today().isoformat(), "color": "Blue", "brand": "", "description": "Blue bottle with a sticker",
}


def signup(c, email):
    r = c.post("/api/auth/register", json={"full_name": "Test User", "email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["user"]["id"]


def test_flow():
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"status": "ok"}

        # reporting requires login
        assert c.post("/api/items", json=GOOD).status_code == 401

        tok, uid = signup(c, "t@x.lk")
        h = {"Authorization": f"Bearer {tok}"}
        assert c.post("/api/auth/register", json={"full_name": "Test User", "email": "t@x.lk", "password": "password123"}).status_code == 409
        assert c.post("/api/auth/login", json={"email": "t@x.lk", "password": "wrong-pass"}).status_code == 401
        assert c.post("/api/auth/login", json={"email": "t@x.lk", "password": "password123"}).status_code == 200
        assert c.get("/api/auth/me", headers=h).json()["email"] == "t@x.lk"

        r = c.post("/api/items", json=GOOD, headers=h)
        assert r.status_code == 201, r.text
        item = r.json()
        assert item["image"] == "/static/placeholder.svg"

        # THE LINK: the new row's owner_id is the logged-in user's id
        with SessionLocal() as db:
            row = db.scalar(select(Item).where(Item.id == item["id"]))
            assert row.owner_id == uid
            assert db.get(User, uid).items[0].id == item["id"]

        # validation
        assert c.post("/api/items", json={**GOOD, "district": "Nowhere"}, headers=h).status_code == 422
        future = (date.today() + timedelta(days=3)).isoformat()
        assert c.post("/api/items", json={**GOOD, "date": future}, headers=h).status_code == 422
        assert c.post("/api/items", json={**GOOD, "type": "Stolen"}, headers=h).status_code == 422

        # upload: owner only, real images only
        files = [("files", ("a.png", PNG, "image/png"))]
        assert c.post(f"/api/items/{item['id']}/images", files=files).status_code == 401
        ok = c.post(f"/api/items/{item['id']}/images", files=files, headers=h)
        assert ok.status_code == 200 and ok.json()["image"].startswith("/uploads/")
        bad = c.post(f"/api/items/{item['id']}/images", files=[("files", ("x.png", b"not an image", "image/png"))], headers=h)
        assert bad.status_code == 400
        assert c.get(ok.json()["image"]).status_code == 200

        # search / filters
        assert len(c.get("/api/items", params={"q": "bottle"}).json()) == 1
        assert c.get("/api/items", params={"type": "Found"}).json() == []

        # my reports + permissions between two users
        assert len(c.get("/api/items/mine", headers=h).json()) == 1
        tok2, _ = signup(c, "other@x.lk")
        h2 = {"Authorization": f"Bearer {tok2}"}
        assert c.get("/api/items/mine", headers=h2).json() == []
        assert c.delete(f"/api/items/{item['id']}", headers=h2).status_code == 403
        assert c.post(f"/api/items/{item['id']}/images", files=files, headers=h2).status_code == 403
        assert c.patch(f"/api/items/{item['id']}/status", json={"status": "Resolved"}, headers=h).status_code == 200
        assert c.get("/api/items").json() == []  # resolved hidden

        # saved
        mine2 = c.post("/api/items", json=GOOD, headers=h).json()
        assert c.put(f"/api/saved/{mine2['id']}", headers=h2).status_code == 204
        assert len(c.get("/api/saved", headers=h2).json()) == 1
        assert c.get("/api/saved").status_code == 401
        assert c.get("/api/admin/stats", headers=h).status_code == 403


# ---------------------------------------------------------------------------
# Chat + notifications
# ---------------------------------------------------------------------------
def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_register_has_no_university_field():
    with TestClient(app) as c:
        r = c.post("/api/auth/register", json={
            "full_name": "Nimal Perera", "email": "nimal@x.lk", "password": "password123",
        })
        assert r.status_code == 201
        assert "university" not in r.json()["user"]
        assert "password_hash" not in r.json()["user"]


def test_chat_and_notifications_flow():
    with TestClient(app) as c:
        owner_tok, owner_id = signup(c, "owner@x.lk")
        finder_tok, finder_id = signup(c, "finder@x.lk")
        stranger_tok, _ = signup(c, "stranger@x.lk")
        owner, finder, stranger = auth(owner_tok), auth(finder_tok), auth(stranger_tok)

        item = c.post("/api/items", json=GOOD, headers=owner).json()
        assert item["owner_id"] == owner_id

        # login required; cannot message yourself; unknown item
        assert c.post("/api/conversations", json={"item_id": item["id"]}).status_code == 401
        assert c.post("/api/conversations", json={"item_id": item["id"]}, headers=owner).status_code == 400
        assert c.post("/api/conversations", json={"item_id": 99999}, headers=finder).status_code == 404

        # finder opens a chat; opening twice returns the SAME chat
        conv = c.post("/api/conversations", json={"item_id": item["id"]}, headers=finder).json()
        again = c.post("/api/conversations", json={"item_id": item["id"]}, headers=finder).json()
        assert conv["id"] == again["id"]
        assert conv["i_am_item_owner"] is False and conv["other_name"] == "Test"
        cid = conv["id"]

        # nothing written yet -> owner sees no chat and gets no notification
        assert c.get("/api/conversations", headers=owner).json() == []
        assert c.get("/api/notifications/summary", headers=owner).json() == {"unread_notifications": 0, "unread_messages": 0}

        # validation
        assert c.post(f"/api/conversations/{cid}/messages", json={"body": "   "}, headers=finder).status_code == 422
        assert c.post(f"/api/conversations/{cid}/messages", json={"body": "x" * 1001}, headers=finder).status_code == 422
        assert c.post(f"/api/conversations/{cid}/messages", json={"body": "hi"}).status_code == 401

        # finder writes -> owner is notified
        m1 = c.post(f"/api/conversations/{cid}/messages", json={"body": "Hi, I found your bottle"}, headers=finder)
        assert m1.status_code == 201 and m1.json()["sender_id"] == finder_id
        assert c.get("/api/notifications/summary", headers=owner).json() == {"unread_notifications": 1, "unread_messages": 1}
        notes = c.get("/api/notifications", headers=owner).json()
        assert len(notes) == 1 and notes[0]["type"] == "message" and notes[0]["conversation_id"] == cid
        assert "Hi, I found your bottle" in notes[0]["body"]
        assert "owner@x.lk" not in str(notes) and "finder@x.lk" not in str(notes)  # no e-mail leaks
        # sender gets nothing for their own message
        assert c.get("/api/notifications/summary", headers=finder).json()["unread_notifications"] == 0

        # a second message refreshes the same notification (no spam)
        c.post(f"/api/conversations/{cid}/messages", json={"body": "Where can we meet?"}, headers=finder)
        notes = c.get("/api/notifications", headers=owner).json()
        assert len(notes) == 1 and "Where can we meet?" in notes[0]["body"]
        assert c.get("/api/notifications/summary", headers=owner).json()["unread_messages"] == 2

        # owner now sees the chat with an unread count
        lst = c.get("/api/conversations", headers=owner).json()
        assert len(lst) == 1 and lst[0]["unread_count"] == 2 and lst[0]["i_am_item_owner"] is True
        assert lst[0]["last_message"]["body"] == "Where can we meet?"

        # privacy: an outsider cannot read, write or even see the chat
        assert c.get(f"/api/conversations/{cid}/messages", headers=stranger).status_code == 404
        assert c.post(f"/api/conversations/{cid}/messages", json={"body": "hey"}, headers=stranger).status_code == 404
        assert c.get(f"/api/conversations/{cid}", headers=stranger).status_code == 404
        assert c.get("/api/conversations", headers=stranger).json() == []

        # owner opens the chat -> messages marked read, notification cleared
        msgs = c.get(f"/api/conversations/{cid}/messages", headers=owner).json()
        assert [m["body"] for m in msgs] == ["Hi, I found your bottle", "Where can we meet?"]
        assert c.get("/api/notifications/summary", headers=owner).json() == {"unread_notifications": 0, "unread_messages": 0}

        # owner replies -> the finder is notified; polling with after_id returns only new ones
        c.post(f"/api/conversations/{cid}/messages", json={"body": "At the library gate"}, headers=owner)
        assert c.get("/api/notifications/summary", headers=finder).json()["unread_notifications"] == 1
        newer = c.get(f"/api/conversations/{cid}/messages", params={"after_id": msgs[-1]["id"]}, headers=finder).json()
        assert [m["body"] for m in newer] == ["At the library gate"]

        # mark-read endpoints (and nobody else's notification can be touched)
        c.post(f"/api/conversations/{cid}/messages", json={"body": "ok?"}, headers=owner)
        nid = c.get("/api/notifications", headers=finder).json()[0]["id"]
        assert c.post(f"/api/notifications/{nid}/read", headers=stranger).status_code == 404
        assert c.post(f"/api/notifications/{nid}/read", headers=finder).status_code == 204
        assert c.get("/api/notifications/summary", headers=finder).json()["unread_notifications"] == 0
        c.post(f"/api/conversations/{cid}/messages", json={"body": "yes"}, headers=owner)
        assert c.post("/api/notifications/read-all", headers=finder).status_code == 204
        assert c.get("/api/notifications/summary", headers=finder).json()["unread_notifications"] == 0

        # resolving the report notifies the other person and blocks NEW chats
        assert c.patch(f"/api/items/{item['id']}/status", json={"status": "Resolved"}, headers=owner).status_code == 200
        notes = c.get("/api/notifications", headers=finder).json()
        assert any(n["type"] == "resolved" for n in notes)
        assert c.post("/api/conversations", json={"item_id": item["id"]}, headers=stranger).status_code == 400
        # ...but the existing chat still works so they can arrange the hand-over
        assert c.post(f"/api/conversations/{cid}/messages", json={"body": "thanks!"}, headers=finder).status_code == 201


def test_deleting_a_report_removes_its_chats():
    with TestClient(app) as c:
        o_tok, _ = signup(c, "o2@x.lk")
        f_tok, _ = signup(c, "f2@x.lk")
        item = c.post("/api/items", json=GOOD, headers=auth(o_tok)).json()
        cid = c.post("/api/conversations", json={"item_id": item["id"]}, headers=auth(f_tok)).json()["id"]
        c.post(f"/api/conversations/{cid}/messages", json={"body": "hello"}, headers=auth(f_tok))
        assert c.delete(f"/api/items/{item['id']}", headers=auth(o_tok)).status_code == 204
        assert c.get(f"/api/conversations/{cid}", headers=auth(f_tok)).status_code == 404
        assert c.get("/api/notifications", headers=auth(o_tok)).json() == []
