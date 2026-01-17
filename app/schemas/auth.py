from pydantic import BaseModel, EmailStr, Field


class SubscriberRegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    remember_me: bool | None = None


class SubscriberLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    remember_me: bool | None = None
