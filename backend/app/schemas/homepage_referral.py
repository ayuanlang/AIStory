from pydantic import BaseModel


class HomepageShareLinkOut(BaseModel):
    referral_token: str
    homepage_path: str
    auth_register_path: str
    issued_at: str