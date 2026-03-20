from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.models.entities import User, UserRole


_GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 0


@dataclass(frozen=True)
class GoogleUserInfo:
    google_id: str
    email: str
    name: str


class GoogleOAuthService:
    """Handles Google OAuth2 login and JWT token issuance."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _build_flow(self) -> Flow:
        client_config: dict[str, Any] = {
            "web": {
                "client_id": self._settings.google_oauth_client_id,
                "client_secret": self._settings.google_oauth_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self._settings.google_oauth_redirect_uri],
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=_GOOGLE_SCOPES,
            redirect_uri=self._settings.google_oauth_redirect_uri,
        )
        return flow

    def get_auth_url(self, state: str | None = None) -> str:
        flow = self._build_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state or "",
        )
        return auth_url

    async def handle_callback(
        self, code: str, db: AsyncSession, org_id: int = 1
    ) -> tuple[User, AuthTokens]:
        flow = self._build_flow()
        flow.fetch_token(code=code)

        credentials = flow.credentials
        id_info = google_id_token.verify_oauth2_token(
            credentials.id_token,
            credentials._request if hasattr(credentials, "_request") else None,
            self._settings.google_oauth_client_id,
            clock_skew_in_seconds=10,
        )

        user_info = GoogleUserInfo(
            google_id=id_info["sub"],
            email=id_info.get("email", ""),
            name=id_info.get("name", ""),
        )

        user = await self._get_or_create_user(db, user_info, org_id)
        tokens = self._create_tokens(user)
        return user, tokens

    async def _get_or_create_user(
        self, db: AsyncSession, info: GoogleUserInfo, org_id: int
    ) -> User:
        stmt = select(User).where(User.google_id == info.google_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is not None:
            return user

        user = User(
            google_id=info.google_id,
            email=info.email,
            name=info.name,
            role=UserRole.sales_rep,
            org_id=org_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    def _create_tokens(self, user: User) -> AuthTokens:
        now = datetime.now(tz=timezone.utc)
        expire_minutes = self._settings.jwt_access_token_expire_minutes
        expires_at = now + timedelta(minutes=expire_minutes)

        payload = {
            "sub": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role.value if isinstance(user.role, UserRole) else user.role,
            "org_id": user.org_id,
            "iat": now,
            "exp": expires_at,
        }
        token = jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )
        return AuthTokens(
            access_token=token,
            expires_in=expire_minutes * 60,
        )

    def verify_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self._settings.jwt_secret_key,
            algorithms=[self._settings.jwt_algorithm],
        )
