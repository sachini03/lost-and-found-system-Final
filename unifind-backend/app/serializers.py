from .models import Item

PLACEHOLDER = "/static/placeholder.svg"


def item_to_dict(item: Item) -> dict:
    images = [img.path for img in item.images]
    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "category": item.category,
        "subcategory": item.subcategory,
        "district": item.district,
        "location": item.location,
        "date": item.date,
        "color": item.color,
        "brand": item.brand,
        "description": item.description,
        "status": item.status,
        "owner_id": item.owner_id,
        "image": images[0] if images else PLACEHOLDER,
        "images": images,
    }
