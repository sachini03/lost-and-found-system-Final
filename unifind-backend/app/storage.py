
import os
from functools import lru_cache

from supabase import Client, create_client

BUCKET = "item-photos"


@lru_cache
def get_storage_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError("Supabase Storage is not configured")

    return create_client(url, key)


def upload_photo(name: str, data: bytes, content_type: str) -> str:
    client = get_storage_client()

    client.storage.from_(BUCKET).upload(
        path=name,
        file=data,
        file_options={
            "content-type": content_type,
            "upsert": "false",
        },
    )

    return client.storage.from_(BUCKET).get_public_url(name)


def delete_photo(url: str) -> None:
    client = get_storage_client()
    public_prefix = f"/storage/v1/object/public/{BUCKET}/"

    if public_prefix not in url:
        return

    name = url.split(public_prefix, 1)[1].split("?", 1)[0]
    client.storage.from_(BUCKET).remove([name])
