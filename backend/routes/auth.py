import os
import re
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from auth_deps import get_token_payload, require_admin
from auth_utils import create_token, hash_password, verify_password
from db import get_database


router = APIRouter()


async def _find_user_by_username(db, username_raw: str):
    """Match username case-insensitively (handles legacy mixed-case rows)."""
    raw = (username_raw or "").strip()
    if not raw:
        return None
    user = await db["users"].find_one({"username": raw})
    if user:
        return user
    safe = re.escape(raw)
    return await db["users"].find_one({"username": {"$regex": f"^{safe}$", "$options": "i"}})


class LoginPayload(BaseModel):
    username: str
    password: str


class RegisterPayload(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: str = "editor"


class AuthUser(BaseModel):
    username: str
    role: str
    email: Optional[str] = None


class UserPublic(BaseModel):
    id: str
    username: str
    role: str
    email: Optional[str] = None
    created_at: Optional[datetime] = None


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: Optional[EmailStr] = None
    password: str = Field(min_length=6, max_length=128)
    role: str = "editor"


class AdminUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)


@router.post("/register", response_model=AuthUser, status_code=201)
async def register(payload: RegisterPayload) -> AuthUser:
    db = get_database()
    username = payload.username.strip().lower()
    role = (payload.role or "editor").strip().lower()
    if role not in ("viewer", "editor", "admin"):
        raise HTTPException(status_code=400, detail="Role must be viewer, editor, or admin")
    exists = await db["users"].find_one({"username": username})
    if exists:
        raise HTTPException(status_code=409, detail="Username already exists")
    await db["users"].insert_one(
        {
            "username": username,
            "email": payload.email,
            "password_hash": hash_password(payload.password),
            "role": role,
            "created_at": datetime.utcnow(),
        }
    )
    return AuthUser(username=username, role=role, email=payload.email)


@router.post("/login")
async def login(payload: LoginPayload) -> dict:
    username = (payload.username or "").strip()
    password = payload.password or ""
    db = get_database()

    env_user = (os.getenv("APP_ADMIN_USERNAME") or "admin").strip()
    env_pwd = os.getenv("APP_ADMIN_PASSWORD") or "admin123"

    # Bootstrap admin (case-insensitive username) — useful when DB is empty or for local dev.
    if username.lower() == env_user.lower() and password == env_pwd:
        token = create_token(username=env_user, role="admin")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"username": env_user, "role": "admin"},
        }

    # DB-backed users (case-insensitive username match).
    user = await _find_user_by_username(db, username)
    if user and verify_password(password, user.get("password_hash", "")):
        canonical = str(user.get("username") or username)
        role = str(user.get("role") or "editor")
        token = create_token(username=canonical, role=role)
        return {"access_token": token, "token_type": "bearer", "user": {"username": canonical, "role": role}}

    raise HTTPException(status_code=401, detail="Invalid username or password")


@router.get("/me", response_model=AuthUser)
async def me(payload: dict = Depends(get_token_payload)) -> AuthUser:
    return AuthUser(username=str(payload.get("username", "")), role=str(payload.get("role", "editor")))


def _serialize_user_public(doc: dict) -> UserPublic:
    return UserPublic(
        id=str(doc["_id"]),
        username=str(doc.get("username", "")),
        role=str(doc.get("role") or "editor"),
        email=doc.get("email"),
        created_at=doc.get("created_at"),
    )


async def _count_admins(db) -> int:
    return await db["users"].count_documents({"role": "admin"})


@router.get("/admin/users", response_model=list[UserPublic])
async def admin_list_users(_admin: dict = Depends(require_admin)) -> list[UserPublic]:
    db = get_database()
    out: list[UserPublic] = []
    async for doc in db["users"].find({}).sort("username", 1):
        out.append(_serialize_user_public(doc))
    return out


@router.post("/admin/users", response_model=UserPublic, status_code=201)
async def admin_create_user(payload: AdminUserCreate, _admin: dict = Depends(require_admin)) -> UserPublic:
    db = get_database()
    username = payload.username.strip().lower()
    role = (payload.role or "editor").strip().lower()
    if role not in ("viewer", "editor", "admin"):
        raise HTTPException(status_code=400, detail="Role must be viewer, editor, or admin")
    exists = await db["users"].find_one({"username": username})
    if exists:
        raise HTTPException(status_code=409, detail="Username already exists")
    result = await db["users"].insert_one(
        {
            "username": username,
            "email": payload.email,
            "password_hash": hash_password(payload.password),
            "role": role,
            "created_at": datetime.utcnow(),
        }
    )
    created = await db["users"].find_one({"_id": result.inserted_id})
    return _serialize_user_public(created)


@router.patch("/admin/users/{user_id}", response_model=UserPublic)
async def admin_update_user(
    user_id: str,
    payload: AdminUserUpdate,
    admin_payload: dict = Depends(require_admin),
) -> UserPublic:
    db = get_database()
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    doc = await db["users"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    updates: dict = {}
    if "email" in data:
        updates["email"] = data["email"]
    if "role" in data and data["role"] is not None:
        new_role = str(data["role"]).strip().lower()
        if new_role not in ("viewer", "editor", "admin"):
            raise HTTPException(status_code=400, detail="Role must be viewer, editor, or admin")
        old_role = str(doc.get("role") or "editor")
        if old_role == "admin" and new_role != "admin":
            admin_count = await _count_admins(db)
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot demote the last database admin user")
        updates["role"] = new_role
    if "password" in data and data["password"] is not None:
        updates["password_hash"] = hash_password(data["password"])

    if not updates:
        return _serialize_user_public(doc)

    updates["updated_at"] = datetime.utcnow()
    updated = await db["users"].find_one_and_update({"_id": oid}, {"$set": updates}, return_document=True)
    return _serialize_user_public(updated)


@router.delete("/admin/users/{user_id}", status_code=204)
async def admin_delete_user(user_id: str, admin_payload: dict = Depends(require_admin)) -> None:
    db = get_database()
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    doc = await db["users"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")

    actor = str(admin_payload.get("username", "")).strip().lower()
    target_name = str(doc.get("username", "")).strip().lower()
    if actor and target_name and actor == target_name:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    if str(doc.get("role") or "editor") == "admin":
        admin_count = await _count_admins(db)
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last database admin user")

    await db["users"].delete_one({"_id": oid})
    return None
