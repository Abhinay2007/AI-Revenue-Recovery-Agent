from fastapi import APIRouter

from app.agent.agent import agent_singleton
from app.agent.schemas import AgentApprovalRequest, AgentChatRequest, AgentResponse

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.get("/status")
def agent_status() -> dict[str, object]:
    return agent_singleton.provider.status()


@router.post("/chat", response_model=AgentResponse)
def agent_chat(request: AgentChatRequest) -> AgentResponse:
    return agent_singleton.chat(request)


@router.post("/approve", response_model=AgentResponse)
def agent_approve(request: AgentApprovalRequest) -> AgentResponse:
    return agent_singleton.approve(request)
