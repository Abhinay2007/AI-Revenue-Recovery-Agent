from fastapi import APIRouter

from app.decision.engine import decide_recovery_action
from app.schemas.recovery import RecoveryDecisionRequest, RecoveryDecisionResponse

router = APIRouter(prefix="/api/v1/recovery", tags=["recovery"])


@router.post("/decision", response_model=RecoveryDecisionResponse)
def create_recovery_decision(request: RecoveryDecisionRequest) -> dict:
    order = {
        "order_id": request.order_id,
        "amount": request.amount,
        "attempt_count": request.attempt_count,
    }
    return decide_recovery_action(order=order, rto_probability=request.rto_probability)

