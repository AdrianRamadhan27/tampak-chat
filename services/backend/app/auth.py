import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Request, Response

from app import db
from app.config import settings
from app.errors import AppError

COOKIE = "tampak_session"
hasher = PasswordHasher()


@dataclass(frozen=True)
class Identity:
    id: str
    kind: str
    csrf: str
    username: str | None = None

    @property
    def scope(self) -> db.Scope:
        return db.Scope(self.id, self.kind == "ADMIN")

    @property
    def admin(self) -> bool:
        return self.kind == "ADMIN"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def current(request: Request, validate_csrf: bool = True) -> Identity:
    token = request.cookies.get(COOKIE, "")
    row = await db.one(
        "SELECT p.*,s.csrf_token FROM sessions s JOIN principals p ON p.id=s.principal_id "
        "WHERE s.token_hash=%s AND s.expires_at>now() "
        "AND (p.expires_at IS NULL OR p.expires_at>now())",
        (token_hash(token),),
    )
    if not row:
        raise AppError("SESSION_REQUIRED", "Start a session to continue.", 401)
    if validate_csrf and request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), row["csrf_token"]):
            raise AppError("CSRF_INVALID", "Refresh the page and try again.", 403)
        check_origin(request)
    return Identity(str(row["id"]), row["kind"], row["csrf_token"], row["username"])


def check_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    allowed = origin is None or origin.rstrip("/") == settings().web_origin.rstrip("/")
    if origin and settings().env == "development":
        candidate, configured = urlparse(origin), urlparse(settings().web_origin)
        allowed = allowed or (
            candidate.hostname in {"localhost", "127.0.0.1"}
            and configured.hostname in {"localhost", "127.0.0.1"}
            and candidate.port == configured.port
            and candidate.scheme == configured.scheme
        )
    if not allowed:
        raise AppError("ORIGIN_INVALID", "This origin is not allowed.", 403)


async def issue(response: Response, principal_id: str, kind: str) -> Identity:
    token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(24)
    expiry = db.now() + timedelta(hours=12 if kind == "ADMIN" else 24)
    await db.execute(
        "INSERT INTO sessions(token_hash,principal_id,csrf_token,expires_at) VALUES(%s,%s,%s,%s)",
        (token_hash(token), principal_id, csrf, expiry),
    )
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings().env == "production",
        max_age=int((expiry - db.now()).total_seconds()),
        path="/",
    )
    return Identity(principal_id, kind, csrf)


async def guest(request: Request, response: Response) -> Identity:
    check_origin(request)
    try:
        return await current(request, validate_csrf=False)
    except AppError as error:
        if error.status != 401:
            raise
    # Anonymous session creation is bounded per network address without retaining it in clear text.
    ip_hash = token_hash(
        (request.client.host if request.client else "local")
        + settings().master_key.get_secret_value()
    )
    count = await db.one(
        "SELECT count(*) AS n FROM audit_events WHERE action='guest.session' "
        "AND detail->>'network'=%s AND created_at>now()-interval '1 hour'",
        (ip_hash,),
    )
    if count and count["n"] >= 30:
        raise AppError("RATE_LIMIT", "Too many demo sessions. Try again later.", 429)
    principal_id = db.new_id()
    await db.execute(
        "INSERT INTO principals(id,kind,expires_at) VALUES(%s,'GUEST',%s)",
        (principal_id, db.now() + timedelta(hours=24)),
    )
    await db.execute(
        "INSERT INTO audit_events(principal_id,action,detail) VALUES(%s,'guest.session',%s)",
        (principal_id, db.jsonb({"network": ip_hash})),
    )
    return await issue(response, principal_id, "GUEST")


async def login(request: Request, response: Response, username: str, password: str) -> Identity:
    check_origin(request)
    ip_hash = token_hash(
        (request.client.host if request.client else "local")
        + settings().master_key.get_secret_value()
    )
    row = await db.one(
        "SELECT count(*) AS n FROM audit_events WHERE action='login.failed' "
        "AND detail->>'network'=%s AND created_at>now()-interval '15 minutes'",
        (ip_hash,),
    )
    if row and row["n"] >= 10:
        raise AppError("RATE_LIMIT", "Too many sign-in attempts. Try again in 15 minutes.", 429)
    principal = await db.one(
        "SELECT * FROM principals WHERE username=%s AND kind='ADMIN'", (username,)
    )
    valid = False
    try:
        valid = hasher.verify(
            principal["password_hash"] if principal else hasher.hash("missing"), password
        )
    except VerificationError:
        pass
    if not valid:
        await db.execute(
            "INSERT INTO audit_events(action,detail) VALUES('login.failed',%s)",
            (db.jsonb({"network": ip_hash}),),
        )
        raise AppError("LOGIN_FAILED", "Username or password is incorrect.", 401)
    return await issue(response, str(principal["id"]), "ADMIN")


async def require_admin(request: Request) -> Identity:
    identity = await current(request)
    if not identity.admin:
        raise AppError("ADMIN_REQUIRED", "Sign in as an administrator.", 403)
    return identity
