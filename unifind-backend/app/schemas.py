from datetime import date as date_type

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .config import CATEGORIES, DISTRICTS


class ItemCreate(BaseModel):
    type: str
    title: str = Field(min_length=2, max_length=160)
    category: str
    subcategory: str = Field(default="", max_length=80)
    district: str
    location: str = Field(default="", max_length=200)
    date: date_type
    color: str = Field(default="", max_length=40)
    brand: str = Field(default="", max_length=80)
    description: str = Field(min_length=3, max_length=2000)

    @field_validator("type")
    @classmethod
    def check_type(cls, v):
        v = v.strip().capitalize()
        if v not in ("Lost", "Found"):
            raise ValueError("type must be 'Lost' or 'Found'")
        return v

    @field_validator("category")
    @classmethod
    def check_category(cls, v):
        if v not in CATEGORIES:
            raise ValueError("Unknown category")
        return v

    @field_validator("district")
    @classmethod
    def check_district(cls, v):
        if v not in DISTRICTS:
            raise ValueError("Unknown district")
        return v

    @field_validator("date")
    @classmethod
    def not_future(cls, v):
        if v > date_type.today():
            raise ValueError("date cannot be in the future")
        return v

    @field_validator("title", "description", "location", "subcategory", "color", "brand")
    @classmethod
    def strip(cls, v):
        return v.strip()


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    category: str
    subcategory: str
    district: str
    location: str
    date: date_type
    color: str
    brand: str
    description: str
    status: str
    owner_id: int | None = None  # lets the frontend hide "contact" on your own report
    image: str            # first image (or placeholder) - what the frontend cards use
    images: list[str]     # every image of the item


class StatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def check(cls, v):
        if v not in ("Active", "Resolved"):
            raise ValueError("status must be 'Active' or 'Resolved'")
        return v


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ConversationCreate(BaseModel):
    item_id: int


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("body")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v
