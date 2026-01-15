from pydantic import BaseModel, EmailStr, Field


class ProfileResponse(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr


class ProfileUpdateRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    new_password_confirm: str = Field(..., min_length=8, max_length=128)
