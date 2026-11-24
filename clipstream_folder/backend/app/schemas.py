"""Request bodies. Pydantic rejects bad input with a 422 before any route code runs."""
from pydantic import BaseModel, Field

MAX_UPLOAD_BYTES = 500 * 1024 * 1024


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class UploadIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    caption: str = Field(default="", max_length=300)
    fileName: str = Field(min_length=1, max_length=255)
    contentType: str = Field(pattern=r"^video/")
    sizeBytes: int = Field(gt=0, le=MAX_UPLOAD_BYTES)
