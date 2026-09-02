from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.integrations.razorpay import RazorpayAPIError, RazorpayConfigurationError, RazorpayMappingError, RazorpayTestModeAdapter

router = APIRouter(prefix="/api/v1/razorpay", tags=["razorpay"])


class RazorpayTestOrderRequest(BaseModel):
    amount: int = Field(gt=0, description="Amount in the smallest currency unit. For INR, Rs 500 is 50000 paise.")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    receipt: str | None = Field(default=None, max_length=40)
    internal_order_id: str | None = Field(default=None, min_length=1)
    notes: dict[str, str] = Field(default_factory=dict)


@router.get("/status")
def razorpay_status() -> dict:
    settings = get_settings()
    try:
        adapter = RazorpayTestModeAdapter.from_settings(settings)
        return adapter.status()
    except RazorpayConfigurationError as exc:
        return {
            "enabled": settings.razorpay_enabled,
            "mode": "test" if settings.razorpay_enabled else "disabled",
            "configured": False,
            "error": str(exc),
        }


@router.get("/connectivity")
def razorpay_connectivity(
    razorpay_order_id: str | None = None,
) -> dict:
    settings = get_settings()
    try:
        adapter = RazorpayTestModeAdapter.from_settings(settings)
    except RazorpayConfigurationError as exc:
        return {
            "enabled": settings.razorpay_enabled,
            "mode": "test" if settings.razorpay_enabled else "disabled",
            "configured": False,
            "reachable": False,
            "authentication_successful": False,
            "requested_test_resource_found": None,
            "operation": "fetch_order" if razorpay_order_id or settings.razorpay_test_order_id else "list_orders",
            "razorpay_order_id_checked": razorpay_order_id or settings.razorpay_test_order_id,
            "error_type": "configuration",
            "error": str(exc),
        }
    return adapter.check_connectivity(razorpay_order_id or settings.razorpay_test_order_id)


@router.post("/test-orders")
def create_razorpay_test_order(request: RazorpayTestOrderRequest) -> dict:
    settings = get_settings()
    try:
        adapter = RazorpayTestModeAdapter.from_settings(settings)
        order = adapter.create_test_order_from_paise(
            amount_paise=request.amount,
            currency=request.currency,
            receipt=request.receipt,
            internal_order_id=request.internal_order_id,
            notes=request.notes,
        )
    except RazorpayConfigurationError as exc:
        return _safe_test_order_error("configuration", str(exc))
    except TimeoutError as exc:
        return _safe_test_order_error("timeout", str(exc))
    except RazorpayAPIError as exc:
        return _safe_test_order_error("api", str(exc))
    return {
        "mode": "test",
        "created": True,
        "internal_order_id": order.get("internal_order_id"),
        "razorpay_order_id": order.get("razorpay_order_id"),
        "receipt": order.get("receipt"),
        "amount": order.get("amount"),
        "currency": order.get("currency"),
        "status": order.get("status"),
        "mapping_created": bool(order.get("internal_order_id") and order.get("razorpay_order_id")),
    }


@router.get("/test-orders/internal/{internal_order_id}")
def fetch_razorpay_test_order_for_internal_order(internal_order_id: str) -> dict:
    settings = get_settings()
    try:
        adapter = RazorpayTestModeAdapter.from_settings(settings)
        result = adapter.fetch_order_for_internal_order(internal_order_id)
    except RazorpayMappingError as exc:
        return {
            "mode": "test" if settings.razorpay_enabled else "disabled",
            "internal_order_id": internal_order_id,
            "found": False,
            "error_type": "mapping_not_found" if "mapping_not_found" in str(exc) else "mapping_mismatch",
            "error": str(exc),
        }
    except RazorpayConfigurationError as exc:
        return _safe_mapped_fetch_error(internal_order_id, "configuration", str(exc), settings.razorpay_enabled)
    except TimeoutError as exc:
        return _safe_mapped_fetch_error(internal_order_id, "timeout", str(exc), settings.razorpay_enabled)
    except RazorpayAPIError as exc:
        return _safe_mapped_fetch_error(internal_order_id, "api", str(exc), settings.razorpay_enabled)
    return {
        "mode": "test",
        "internal_order_id": internal_order_id,
        "found": True,
        **result,
    }


def _safe_test_order_error(error_type: str, message: str) -> dict:
    return {
        "mode": "test",
        "created": False,
        "razorpay_order_id": None,
        "error_type": error_type,
        "error": message,
    }


def _safe_mapped_fetch_error(internal_order_id: str, error_type: str, message: str, enabled: bool) -> dict:
    return {
        "mode": "test" if enabled else "disabled",
        "internal_order_id": internal_order_id,
        "found": False,
        "error_type": error_type,
        "error": message,
    }
