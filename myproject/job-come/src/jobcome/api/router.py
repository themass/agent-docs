"""API router aggregation."""

from fastapi import APIRouter

from jobcome.api.admin_router import router as admin_router
from jobcome.api.auth_router import router as auth_router
from jobcome.api.agent_router import router as agent_router
from jobcome.api.campaign_router import router as campaign_router
from jobcome.api.coach_router import router as coach_router
from jobcome.api.guest_router import router as guest_router
from jobcome.api.jobs_router import router as jobs_router
from jobcome.api.notification_router import router as notification_router
from jobcome.api.profile_router import router as profile_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(agent_router)
api_router.include_router(coach_router)
api_router.include_router(campaign_router)
api_router.include_router(jobs_router)
api_router.include_router(guest_router)
api_router.include_router(profile_router)
api_router.include_router(notification_router)
