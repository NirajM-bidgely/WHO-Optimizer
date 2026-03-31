"""MILP: pick one feasible start per shiftable block to minimize sum of block energy costs."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from pulp import LpMinimize, LpProblem, LpStatus, lpSum, LpVariable, PULP_CBC_CMD

from app.feasible import feasible_starts, slots_per_day_from_granularity
from app.models import (
    ApplianceBlock,
    ApplianceShiftResult,
    BlockShiftResult,
    OptimizeRequest,
    OptimizeResponse,
    OutputMetadata,
)

logger = logging.getLogger(__name__)


def _fmt_int_list(xs: list[int], head: int = 36) -> str:
    if len(xs) <= head:
        return str(xs)
    return f"{xs[:head]}... (+{len(xs) - head} more)"


def block_energy_cost(
    rate_vector: list[float], start_t: int, consumption: list[float]
) -> float:
    total = 0.0
    for k, c in enumerate(consumption):
        idx = start_t + k
        if idx < 0 or idx >= len(rate_vector):
            raise ValueError(f"start_t {start_t} with offset {k} out of rate vector bounds")
        total += rate_vector[idx] * c
    return total


@dataclass(frozen=True)
class ShiftableBlockRef:
    app_id: int
    block: ApplianceBlock


def _collect_shiftable(request: OptimizeRequest) -> list[ShiftableBlockRef]:
    refs: list[ShiftableBlockRef] = []
    for app in request.appliances:
        if not app.shiftable:
            continue
        for b in app.blocks:
            refs.append(ShiftableBlockRef(app_id=app.appId, block=b))
    return refs


def optimize(request: OptimizeRequest, default_currency: str = "INR") -> OptimizeResponse:
    rates = request.rates.rateVector
    T = request.metadata.totalTimeSlots
    currency = request.metadata.currency or default_currency
    slots_per_day = slots_per_day_from_granularity(request.metadata.granularity)

    logger.debug(
        "optimize begin horizon=%s slots_per_day=%s (granularity=%s) shiftable_blocks=%s",
        T,
        slots_per_day,
        request.metadata.granularity,
        sum(len(a.blocks) for a in request.appliances if a.shiftable),
    )

    refs = _collect_shiftable(request)
    if not refs:
        return OptimizeResponse(
            metadata=OutputMetadata(
                granularity=request.metadata.granularity,
                totalTimeSlots=T,
                currency=currency,
            ),
            loadShift=[],
        )

    feasible_per_ref: list[list[int]] = []
    for ref in refs:
        S = feasible_starts(ref.block, T, slots_per_day=slots_per_day)
        if not S:
            raise ValueError(
                f"No feasible start for shiftable block appId={ref.app_id} "
                f"blockId={ref.block.blockId}"
            )
        feasible_per_ref.append(S)
        logger.debug(
            "MILP ref i=%s appId=%s blockId=%s feasible_count=%s feasible_starts=%s",
            len(feasible_per_ref) - 1,
            ref.app_id,
            ref.block.blockId,
            len(S),
            _fmt_int_list(S),
        )

    prob = LpProblem("tou_shift", LpMinimize)
    x_vars: list[list] = []
    obj_terms = []

    for i, ref in enumerate(refs):
        S = feasible_per_ref[i]
        xs = [LpVariable(f"x_{i}_{s}", cat="Binary") for s in S]
        x_vars.append(list(zip(S, xs)))
        prob += lpSum(x[1] for x in zip(S, xs)) == 1
        b = ref.block
        for s, xv in zip(S, xs):
            cost_s = block_energy_cost(rates, s, b.consumption)
            obj_terms.append(cost_s * xv)

    prob += lpSum(obj_terms)

    prob.solve(PULP_CBC_CMD(msg=False))
    logger.debug("MILP solver status=%s", LpStatus[prob.status])
    if LpStatus[prob.status] != "Optimal":
        raise RuntimeError(f"MILP solver status: {LpStatus[prob.status]}")

    chosen: list[int] = []
    for i, ref in enumerate(refs):
        S = feasible_per_ref[i]
        xs = x_vars[i]
        found = None
        for s, xv in xs:
            if xv.varValue is not None and xv.varValue > 0.5:
                found = s
                break
        if found is None:
            raise RuntimeError(f"No solution extracted for block index {i}")
        chosen.append(found)
        logger.debug(
            "MILP solution ref i=%s appId=%s blockId=%s originalStart=%s newStart=%s",
            i,
            ref.app_id,
            ref.block.blockId,
            ref.block.start_t,
            found,
        )

    by_app: dict[int, list[tuple[ApplianceBlock, int]]] = defaultdict(list)
    for ref, new_start in zip(refs, chosen):
        by_app[ref.app_id].append((ref.block, new_start))

    load_shift: list[ApplianceShiftResult] = []
    for app_id in sorted(by_app.keys()):
        block_results: list[BlockShiftResult] = []
        total_savings = 0.0
        for b, new_start in by_app[app_id]:
            cost_before = block_energy_cost(rates, b.start_t, b.consumption)
            cost_after = block_energy_cost(rates, new_start, b.consumption)
            raw_sav = cost_before - cost_after
            sav = round(raw_sav, 6)
            if sav == 0.0:
                continue
            total_savings += sav
            block_results.append(
                BlockShiftResult(
                    blockId=b.blockId,
                    originalStart_t=b.start_t,
                    newStart_t=new_start,
                    duration=b.duration,
                    consumption=list(b.consumption),
                    costBefore=round(cost_before, 6),
                    costAfter=round(cost_after, 6),
                    savings=sav,
                )
            )
        if not block_results:
            continue
        load_shift.append(
            ApplianceShiftResult(
                appId=app_id,
                totalSavings=round(total_savings, 6),
                blockShifts=block_results,
            )
        )

    return OptimizeResponse(
        metadata=OutputMetadata(
            granularity=request.metadata.granularity,
            totalTimeSlots=T,
            currency=currency,
        ),
        loadShift=load_shift,
    )
