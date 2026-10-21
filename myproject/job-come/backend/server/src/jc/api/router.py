"""API router aggregation."""

from fastapi import APIRouter

from jc.api.admin_router import router as admin_router
from jc.api.agent_router import router as agent_router
from jc.api.auth_router import router as auth_router
from jc.api.campaign_router import router as campaign_router
from jc.api.coach_router import router as coach_router
from jc.api.feedback_router import router as feedback_router
from jc.api.guest_router import router as guest_router
from jc.api.jobs_router import router as jobs_router
from jc.api.notification_router import router as notification_router
from jc.api.profile_router import router as profile_router
from jc.api.storage_router import router as storage_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(agent_router)
api_router.include_router(coach_router)
api_router.include_router(campaign_router)
api_router.include_router(jobs_router)
api_router.include_router(guest_router)
api_router.include_router(profile_router)
api_router.include_router(storage_router)
api_router.include_router(notification_router)
api_router.include_router(feedback_router)
