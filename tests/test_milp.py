from app.milp import block_energy_cost, optimize
from app.models import (
    Appliance,
    ApplianceBlock,
    BlockConstraints,
    InputMetadata,
    OptimizeRequest,
    Rates,
)


def test_optimize_shifts_to_cheap_slot():
    req = OptimizeRequest(
        metadata=InputMetadata(
            granularity=3600,
            startTime=0,
            totalTimeSlots=24,
            timezone="UTC",
        ),
        rates=Rates(
            rateVector=[1.0] + [10.0] * 23,
        ),
        appliances=[
            Appliance(
                appId=71,
                name="AC",
                shiftable=True,
                blocks=[
                    ApplianceBlock(
                        blockId=1,
                        start_t=5,
                        duration=1,
                        consumption=[2.0],
                        constraints=BlockConstraints(maxShiftHours=10),
                    )
                ],
            )
        ],
    )
    out = optimize(req)
    assert out.loadShift[0].blockShifts[0].newStart_t == 0
    assert out.loadShift[0].blockShifts[0].costBefore == 20.0
    assert out.loadShift[0].blockShifts[0].costAfter == 2.0
    assert out.loadShift[0].blockShifts[0].savings == 18.0
    assert out.metadata.currency == "INR"


def test_optimize_cannot_jump_to_cheaper_slot_on_another_day():
    """Slot 0 is cheapest overall but on day 0; block on day 1 must use day-1 minimum (slot 24)."""
    rates = [1.0] + [10.0] * 23 + [1.0] + [10.0] * 23
    req = OptimizeRequest(
        metadata=InputMetadata(
            granularity=3600,
            startTime=0,
            totalTimeSlots=48,
            timezone="UTC",
        ),
        rates=Rates(rateVector=rates),
        appliances=[
            Appliance(
                appId=71,
                name="AC",
                shiftable=True,
                blocks=[
                    ApplianceBlock(
                        blockId=1,
                        start_t=30,
                        duration=1,
                        consumption=[1.0],
                        constraints=None,
                    )
                ],
            )
        ],
    )
    out = optimize(req)
    # Unique cheapest within day 1 is slot 24 (rate 1.0); cannot use slot 0 on day 0.
    assert out.loadShift[0].blockShifts[0].newStart_t == 24
    assert out.loadShift[0].blockShifts[0].costAfter == 1.0
    assert out.loadShift[0].blockShifts[0].costBefore == 10.0


def test_two_shiftable_blocks_day0_and_day1_cheapest_per_day():
    """Regression: block on day 1 (start_t=28) must not move to slot 0; cheapest in-window is 24."""
    rates = [
        1.0,
        *[10.0] * 23,
        1.0,
        *[10.0] * 23,
    ]
    req = OptimizeRequest(
        metadata=InputMetadata(
            granularity=3600,
            startTime=1709251200,
            totalTimeSlots=48,
            timezone="Asia/Kolkata",
            currency="USD",
        ),
        rates=Rates(rateVector=rates),
        appliances=[
            Appliance(
                appId=71,
                name="AC",
                shiftable=True,
                blocks=[
                    ApplianceBlock(
                        blockId=1,
                        start_t=5,
                        duration=1,
                        consumption=[2.0],
                        constraints=BlockConstraints(maxShiftHours=10),
                    ),
                    ApplianceBlock(
                        blockId=2,
                        start_t=28,
                        duration=1,
                        consumption=[3.0],
                        constraints=None,
                    ),
                ],
            )
        ],
    )
    out = optimize(req)
    assert out.metadata.currency == "USD"
    shifts = {b.blockId: b for b in out.loadShift[0].blockShifts}
    assert shifts[1].newStart_t == 0
    assert shifts[2].newStart_t == 24
    assert out.loadShift[0].totalSavings == 45.0


def test_block_energy_cost():
    rv = [1.0, 2.0, 3.0]
    assert block_energy_cost(rv, 0, [1.0, 1.0]) == 3.0
