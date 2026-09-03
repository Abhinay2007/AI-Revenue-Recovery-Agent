from fastapi import APIRouter

from app.agent.agent import agent_singleton

router = APIRouter(prefix="/api/v1/merchant", tags=["merchant"])


@router.get("/analytics")
def merchant_analytics() -> dict:
    return agent_singleton.tools.merchant_tool.get_dashboard_analytics()