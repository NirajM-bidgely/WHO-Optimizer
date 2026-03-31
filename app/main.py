"""FastAPI app: POST /optimize, GET /health."""

from __future__ import annotations

import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.logging_config import configure_logging
from app.milp import optimize
from app.models import OptimizeRequest, OptimizeResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info(
        "TOU optimizer ready — POST /optimize logs at INFO; LOG_LEVEL=DEBUG for feasible/MILP traces"
    )
    yield


app = FastAPI(
    title="TOU load-shift optimizer",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/optimize", response_model=OptimizeResponse)
def post_optimize(body: OptimizeRequest) -> OptimizeResponse:
    shiftable = sum(len(a.blocks) for a in body.appliances if a.shiftable)
    logger.info(
        "POST /optimize totalTimeSlots=%s granularity=%s shiftable_block_count=%s",
        body.metadata.totalTimeSlots,
        body.metadata.granularity,
        shiftable,
    )
    logger.debug(
        "POST /optimize detail timezone=%s",
        body.metadata.timezone,
    )
    try:
        out = optimize(body)
        logger.info(
            "POST /optimize ok loadShift_apps=%s",
            len(out.loadShift),
        )
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
