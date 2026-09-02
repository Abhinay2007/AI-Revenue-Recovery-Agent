from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx

from app.core.config import Settings


class RazorpayConfigurationError(RuntimeError):
    """Raised when Razorpay Test Mode is enabled with unsafe or missing config."""


class RazorpayAPIError(RuntimeError):
    """Raised when Razorpay returns an API error or malformed response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class RazorpayIdentifierMapping:
    internal_order_id: str
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    receipt: str | None = None

    def as_safe_dict(self) -> dict[str, Any]:
        return {
            "internal_order_id": self.internal_order_id,
            "razorpay_order_id": self.razorpay_order_id,
            "razorpay_payment_id": self.razorpay_payment_id,
            "receipt": self.receipt,
        }


class RazorpayMappingError(RuntimeError):
    pass


class InMemoryRazorpayMappingStore:
    """Demo-only mapping store. Durable persistence belongs in a later milestone."""

    def __init__(self) -> None:
        self._by_internal_order_id: dict[str, RazorpayIdentifierMapping] = {}

    def save(self, mapping: RazorpayIdentifierMapping) -> RazorpayIdentifierMapping:
        self._by_internal_order_id[mapping.internal_order_id] = mapping
        return mapping

    def get(self, internal_order_id: str) -> RazorpayIdentifierMapping | None:
        return self._by_internal_order_id.get(internal_order_id)

    def clear(self) -> None:
        self._by_internal_order_id.clear()


razorpay_mapping_store = InMemoryRazorpayMappingStore()


class DemoRazorpayOrderMapper:
    """Deterministic mapping helper for synthetic internal order IDs.

    Synthetic IDs such as ORD-0042-0009754 are not Razorpay order IDs. For demo
    test orders we map them into a deterministic Razorpay receipt.
    """

    @staticmethod
    def receipt_for_internal_order(internal_order_id: str) -> str:
        cleaned = internal_order_id.replace(" ", "").upper()
        return f"rr_{cleaned}"[:40]

    def build_mapping(
        self,
        internal_order_id: str,
        razorpay_order_id: str | None = None,
        razorpay_payment_id: str | None = None,
    ) -> RazorpayIdentifierMapping:
        return RazorpayIdentifierMapping(
            internal_order_id=internal_order_id,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            receipt=self.receipt_for_internal_order(internal_order_id),
        )


class RazorpayTestModeAdapter:
    def __init__(
        self,
        key_id: str | None,
        key_secret: str | None,
        enabled: bool = False,
        timeout_seconds: float = 10.0,
        base_url: str = "https://api.razorpay.com/v1",
        client: httpx.Client | None = None,
        mapper: DemoRazorpayOrderMapper | None = None,
        mapping_store: InMemoryRazorpayMappingStore = razorpay_mapping_store,
    ) -> None:
        self.enabled = enabled
        self.key_id = key_id or ""
        self._key_secret = key_secret or ""
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self.mapper = mapper or DemoRazorpayOrderMapper()
        self.mapping_store = mapping_store
        self._validate_configuration()

    @classmethod
    def from_settings(cls, settings: Settings, client: httpx.Client | None = None) -> RazorpayTestModeAdapter:
        return cls(
            key_id=settings.razorpay_key_id,
            key_secret=settings.razorpay_key_secret,
            enabled=settings.razorpay_enabled,
            timeout_seconds=settings.razorpay_request_timeout_seconds,
            client=client,
        )

    def _validate_configuration(self) -> None:
        if not self.enabled:
            return
        if not self.key_id or not self._key_secret:
            raise RazorpayConfigurationError("Razorpay Test Mode is enabled but credentials are missing")
        if self.key_id.startswith("rzp_live_") or self._key_secret.startswith("rzp_live_"):
            raise RazorpayConfigurationError("Live Razorpay keys are not allowed")
        if not self.key_id.startswith("rzp_test_"):
            raise RazorpayConfigurationError("Razorpay Test Mode requires an rzp_test_ key ID")

    def status(self) -> dict[str, Any]:
        configured = bool(self.enabled and self.key_id and self._key_secret)
        return {
            "enabled": self.enabled,
            "mode": "test" if self.enabled else "disabled",
            "configured": configured,
            "key_id_prefix": self.key_id[:8] if configured else None,
        }

    def fetch_order(self, razorpay_order_id: str) -> dict[str, Any]:
        self._require_enabled()
        return self._request("GET", f"/orders/{razorpay_order_id}")

    def fetch_payment(self, razorpay_payment_id: str) -> dict[str, Any]:
        self._require_enabled()
        return self._request("GET", f"/payments/{razorpay_payment_id}")

    def list_orders(self, count: int = 1) -> dict[str, Any]:
        self._require_enabled()
        bounded_count = max(1, min(count, 10))
        return self._request("GET", "/orders", params={"count": bounded_count})

    def check_connectivity(self, razorpay_order_id: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "enabled": self.enabled,
            "mode": "test" if self.enabled else "disabled",
            "configured": bool(self.enabled and self.key_id and self._key_secret),
            "reachable": False,
            "authentication_successful": False,
            "requested_test_resource_found": None,
            "operation": "fetch_order" if razorpay_order_id else "list_orders",
            "razorpay_order_id_checked": razorpay_order_id,
            "error_type": None,
            "error": None,
        }
        try:
            if razorpay_order_id:
                payload = self.fetch_order(razorpay_order_id)
                result["requested_test_resource_found"] = bool(payload.get("id") == razorpay_order_id)
            else:
                self.list_orders(count=1)
            result["reachable"] = True
            result["authentication_successful"] = True
            return result
        except RazorpayConfigurationError as exc:
            result["error_type"] = "configuration"
            result["error"] = str(exc)
            return result
        except TimeoutError as exc:
            result["error_type"] = "timeout"
            result["error"] = str(exc)
            return result
        except RazorpayAPIError as exc:
            result["reachable"] = exc.status_code is not None
            if exc.status_code == 401:
                result["error_type"] = "authentication"
                result["error"] = "Razorpay Test Mode authentication failed"
            elif razorpay_order_id and exc.status_code in {400, 404}:
                result["authentication_successful"] = True
                result["requested_test_resource_found"] = False
                result["error_type"] = "not_found"
                result["error"] = "Requested Razorpay test order was not found"
            else:
                result["error_type"] = "api"
                result["error"] = str(exc)
            return result

    def create_test_order(
        self,
        internal_order_id: str,
        amount_rupees: Decimal,
        currency: str = "INR",
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        amount_paise = self._rupees_to_paise(amount_rupees)
        receipt = self.mapper.receipt_for_internal_order(internal_order_id)
        return self.create_test_order_from_paise(
            amount_paise=amount_paise,
            currency=currency,
            receipt=receipt,
            internal_order_id=internal_order_id,
            notes=notes,
        )

    def create_test_order_from_paise(
        self,
        amount_paise: int,
        currency: str = "INR",
        receipt: str | None = None,
        internal_order_id: str | None = None,
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._require_enabled()
        if amount_paise <= 0:
            raise RazorpayConfigurationError("Razorpay test order amount must be positive")
        if not currency:
            raise RazorpayConfigurationError("Razorpay test order currency is required")
        resolved_receipt = receipt or (self.mapper.receipt_for_internal_order(internal_order_id) if internal_order_id else "rr_demo_test_order")
        payload = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": resolved_receipt,
            "notes": {
                **({"internal_order_id": internal_order_id} if internal_order_id else {}),
                "source": "ai_revenue_recovery_agent_test_mode",
                **(notes or {}),
            },
        }
        response = self._request("POST", "/orders", json=payload)
        razorpay_order_id = response.get("id")
        if internal_order_id and razorpay_order_id:
            self.mapping_store.save(
                RazorpayIdentifierMapping(
                    internal_order_id=internal_order_id,
                    razorpay_order_id=str(razorpay_order_id),
                    razorpay_payment_id=None,
                    receipt=response.get("receipt") or resolved_receipt,
                )
            )
        return {
            "internal_order_id": internal_order_id,
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": None,
            "receipt": response.get("receipt") or resolved_receipt,
            "amount": response.get("amount", amount_paise),
            "currency": response.get("currency", currency),
            "status": response.get("status"),
            "mode": "test",
        }

    def get_mapping(self, internal_order_id: str) -> dict[str, Any]:
        mapping = self.mapping_store.get(internal_order_id)
        if mapping is None:
            raise RazorpayMappingError(f"mapping_not_found: {internal_order_id}")
        return mapping.as_safe_dict()

    def fetch_order_for_internal_order(self, internal_order_id: str) -> dict[str, Any]:
        mapping = self.mapping_store.get(internal_order_id)
        if mapping is None or not mapping.razorpay_order_id:
            raise RazorpayMappingError(f"mapping_not_found: {internal_order_id}")
        order = self.fetch_order(mapping.razorpay_order_id)
        if order.get("id") != mapping.razorpay_order_id:
            raise RazorpayMappingError("mapped Razorpay order ID did not match fetched order")
        return {
            "mode": "test",
            "internal_order_id": internal_order_id,
            "mapping": mapping.as_safe_dict(),
            "razorpay_order": {
                "id": order.get("id"),
                "amount": order.get("amount"),
                "currency": order.get("currency"),
                "receipt": order.get("receipt"),
                "status": order.get("status"),
            },
        }

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self.client.request(
                method,
                f"{self.base_url}{path}",
                auth=(self.key_id, self._key_secret),
                json=json,
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError("Razorpay Test Mode request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise RazorpayAPIError(
                f"Razorpay Test Mode API error: HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise RazorpayAPIError("Razorpay Test Mode request failed") from exc
        payload = response.json()
        if not isinstance(payload, dict):
            raise RazorpayAPIError("Razorpay Test Mode returned a malformed response")
        return payload

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise RazorpayConfigurationError("Razorpay Test Mode integration is disabled")

    @staticmethod
    def _rupees_to_paise(value: Decimal) -> int:
        paise = (value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(paise)
