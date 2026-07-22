from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    # Email is unique per-org, not globally, so org_id disambiguates which
    # account "email" refers to. A slug-based lookup can replace this once
    # the frontend needs a friendlier login form (no backend change required).
    org_id: int
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
