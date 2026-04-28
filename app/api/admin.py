"""
Admin / Developer Dashboard Routes
==================================
Endpoints for developers to manage their API keys.
Secured by Clerk OAuth JWTs, not by API keys.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.api.dependencies import get_clerk_user
from app import auth, db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/keys", tags=["Admin"])

class CreateKeyRequest(BaseModel):
    name: str = "Default Key"

class KeyResponse(BaseModel):
    id: str
    name: str
    masked_key: str
    created_at: str

@router.post(
    "/generate", 
    summary="Generate a new API key",
    description="Creates a new API key for the logged-in user. The raw key is returned exactly ONCE."
)
async def generate_api_key(
    request: CreateKeyRequest, 
    user: dict = Depends(get_clerk_user)
):
    # Generate key material in the auth module (pure logic, no DB)
    raw_key = auth.generate_raw_api_key()
    key_hash = auth.hash_api_key(raw_key)
    masked_key = auth.mask_api_key(raw_key)

    # Persist to DB via the users repository
    key_id = await db.create_api_key_for_user(
        user_id=user["id"],
        key_hash=key_hash,
        masked_key=masked_key,
        name=request.name,
    )

    if not key_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate API key."
        )

    return {
        "message": "Key generated successfully. Please copy it now, it will not be shown again.",
        "id": key_id,
        "name": request.name,
        "masked_key": masked_key,
        "raw_key": raw_key  # CAUTION: Store this immediately
    }

@router.get(
    "",
    summary="List active API keys",
    description="Returns all active, masked API keys for the logged-in user."
)
async def list_api_keys(user: dict = Depends(get_clerk_user)):
    keys = await db.list_user_keys(user_id=user["id"])
    
    # Convert datetime to ISO strings for JSON serialization
    for k in keys:
        if "created_at" in k and k["created_at"]:
            k["created_at"] = k["created_at"].isoformat()
            
    return {"keys": keys}

@router.delete(
    "/{key_id}",
    summary="Revoke an API key",
    description="Permanently disables the specified API key."
)
async def revoke_api_key(key_id: str, user: dict = Depends(get_clerk_user)):
    success = await db.revoke_api_key(key_id=key_id, user_id=user["id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Key not found or already revoked."
        )
    return {"message": "Key successfully revoked."}
