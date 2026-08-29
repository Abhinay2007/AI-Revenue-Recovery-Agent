from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.health import check_database_health

router = APIRouter(prefix="/api/v1", tags=["database"])


@router.get("/db/health")
def database_health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        check_database_health(db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return {"status": "ok"}

