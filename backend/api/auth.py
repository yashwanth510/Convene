import asyncio
import hashlib
import hmac
import secrets
import time
import uuid
from collections import deque
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from backend.config import config
from backend.storage.database import users, sessions

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=256)
    invite_code: str = Field(default="", max_length=256)

    @field_validator("email")
    @classmethod
    def email_address(cls, value):
        value = value.strip().lower()
        if (
            value.count("@") != 1
            or "." not in value.split("@")[-1]
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Enter a valid email address")
        return value


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 600000
    ).hex()
    return salt + ":" + digest


async def current_user(
    request: Request, auth: HTTPAuthorizationCredentials | None = Depends(bearer)
):
    user = await request.app.state.db.user_for_token(auth.credentials) if auth else None
    if not user:
        raise HTTPException(401, "Please sign in to continue")
    return {**user, "is_admin": user["id"] in config.ADMIN_USER_IDS}


async def current_admin(user=Depends(current_user)):
    if not user["is_admin"]:
        raise HTTPException(403, "Administrator access required")
    return user


def throttle(request):
    # One app process per deployment; cap password-hash work before running it.
    key = request.client.host if request.client else "unknown"
    buckets = request.app.state.auth_attempts
    now = time.monotonic()
    if len(buckets) > 2048:
        expired = [k for k, v in buckets.items() if not v or v[-1] < now - 300]
        for k in expired:
            del buckets[k]
        if len(buckets) > 2048:
            raise HTTPException(429, "Please try again later")
    attempts = buckets.setdefault(key, deque())
    while attempts and attempts[0] < now - 300:
        attempts.popleft()
    if len(attempts) >= 15:
        raise HTTPException(
            429, "Too many sign-in attempts. Try again in five minutes."
        )
    attempts.append(now)


async def issue_session(db, uid, email):
    token = secrets.token_urlsafe(48)
    async with db.engine.begin() as c:
        await c.execute(delete(sessions).where(sessions.c.expires < time.time()))
        await c.execute(
            sessions.insert().values(
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=uid,
                expires=time.time() + config.SESSION_DAYS * 86400,
            )
        )
    return {
        "token": token,
        "user": {"id": uid, "email": email, "is_admin": uid in config.ADMIN_USER_IDS},
    }


@router.post("/register", status_code=201)
async def register(body: Credentials, request: Request):
    throttle(request)
    if config.INVITE_CODE and not hmac.compare_digest(
        body.invite_code, config.INVITE_CODE
    ):
        raise HTTPException(403, "A valid invite code is required")
    db = request.app.state.db
    hashed = await asyncio.to_thread(password_hash, body.password)
    uid = str(uuid.uuid4())
    try:
        async with db.engine.begin() as c:
            await c.execute(
                users.insert().values(
                    id=uid, email=body.email, password=hashed, created=time.time()
                )
            )
    except IntegrityError:
        raise HTTPException(409, "An account with that email already exists") from None
    return await issue_session(db, uid, body.email)


@router.post("/login")
async def login(body: Credentials, request: Request):
    throttle(request)
    db = request.app.state.db
    async with db.engine.connect() as c:
        row = (
            (await c.execute(select(users).where(users.c.email == body.email)))
            .mappings()
            .first()
        )
    salt = row["password"].split(":")[0] if row else "00" * 16
    candidate = await asyncio.to_thread(password_hash, body.password, salt)
    if not row or not hmac.compare_digest(candidate, row["password"]):
        raise HTTPException(401, "Email or password is incorrect")
    return await issue_session(db, row["id"], row["email"])


@router.get("/me")
async def me(user=Depends(current_user)):
    return user


@router.post("/logout", status_code=204)
async def logout(request: Request, user=Depends(current_user), auth=Depends(bearer)):
    async with request.app.state.db.engine.begin() as c:
        await c.execute(
            delete(sessions).where(
                sessions.c.token_hash
                == hashlib.sha256(auth.credentials.encode()).hexdigest()
            )
        )
