"""
src/simulation/reactive_devices.py

Reactive compensation devices for the GRIDCOM voltage model: automatic
shunt capacitor/reactor banks, automatic transformer taps, and a manual
SVC/STATCOM. All three are modelled as Q injections at a bus — none of
them edit B' or trigger a matrix rebuild.

Automatic devices (ShuntBank, TransformerTap) are controlled by
step_automatics(), called once per tick before the Q injections are built.
They read the *previous* tick's solved voltage (one-tick lag — no
algebraic loop with the solver) and step toward their deadband, gated by
a minimum dwell time to prevent hunting.

The manual SVC is set directly by the player via GridSimulation.set_svc_setpoint().

See VOLTAGE_REACTIVE_PLAN.md Phase C and GRID_SIMULATION_MECHANICS.md §5
for the design rationale.
"""

from dataclasses import dataclass, field

from simulation.constants import (
    SHUNT_BANK_MVAR_PER_STEP, SHUNT_BANK_MAX_STEPS,
    SHUNT_DEADBAND_LOW_PU, SHUNT_DEADBAND_HIGH_PU, SHUNT_SWITCH_DWELL_S,
    TAP_STEP_RATIO, TAP_N_STEPS, TAP_NEUTRAL_STEP,
    TAP_DEADBAND_LOW_PU, TAP_DEADBAND_HIGH_PU, TAP_DWELL_S,
    SVC_Q_MIN_MVAR, SVC_Q_MAX_MVAR,
)

BusLabel = str


# ─────────────────────────────────────────────────────────────────────────────
# AUTOMATIC SHUNT CAPACITOR / REACTOR BANK
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ShuntBank:
    """
    Automatic shunt capacitor/reactor bank at a bus. Steps toward the
    bus's voltage deadband; +step = capacitive (raises V), -step = reactive
    (lowers V). Player cannot control this directly — read-only display.
    """
    bus: BusLabel
    mvar_per_step: float = SHUNT_BANK_MVAR_PER_STEP
    max_steps: int = SHUNT_BANK_MAX_STEPS
    step: int = 0                    # signed: -max_steps..+max_steps
    _dwell_remaining_s: float = field(default=0.0, repr=False)

    @property
    def mvar(self) -> float:
        return self.step * self.mvar_per_step

    def tick_dwell(self, dt_sim_seconds: float) -> None:
        if self._dwell_remaining_s > 0.0:
            self._dwell_remaining_s = max(0.0, self._dwell_remaining_s - dt_sim_seconds)

    def maybe_switch(self, bus_voltage: float, dt_sim_seconds: float) -> bool:
        """
        If bus_voltage is outside the deadband and the dwell timer has
        elapsed, step one increment toward the deadband. Returns True if
        a switch occurred this call.
        """
        self.tick_dwell(dt_sim_seconds)
        if self._dwell_remaining_s > 0.0:
            return False

        if bus_voltage < SHUNT_DEADBAND_LOW_PU and self.step < self.max_steps:
            self.step += 1
            self._dwell_remaining_s = SHUNT_SWITCH_DWELL_S
            return True
        if bus_voltage > SHUNT_DEADBAND_HIGH_PU and self.step > -self.max_steps:
            self.step -= 1
            self._dwell_remaining_s = SHUNT_SWITCH_DWELL_S
            return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# AUTOMATIC TRANSFORMER TAP CHANGER (Q approximation)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TransformerTap:
    """
    Automatic tap changer regulating a bus's voltage. Modelled as a
    corrective Q injection approximating the ΔV a real tap step would
    produce: ΔQ_mvar = b_diag(regulated_bus) * (tap_step * TAP_STEP_RATIO) * S_BASE,
    computed by GridSimulation via VoltageModel.b_diag(). Discrete steps,
    B' itself is untouched. Documented approximation — true voltage-ratio
    tap modelling is a flagged follow-up, not this pass.
    """
    label: BusLabel
    regulated_bus: BusLabel
    step: int = TAP_NEUTRAL_STEP     # signed: -n_steps..+n_steps
    n_steps: int = TAP_N_STEPS
    step_ratio: float = TAP_STEP_RATIO
    neutral_step: int = TAP_NEUTRAL_STEP
    _dwell_remaining_s: float = field(default=0.0, repr=False)

    @property
    def delta_v_pu(self) -> float:
        """Approximate voltage correction this tap position contributes."""
        return (self.step - self.neutral_step) * self.step_ratio

    def tick_dwell(self, dt_sim_seconds: float) -> None:
        if self._dwell_remaining_s > 0.0:
            self._dwell_remaining_s = max(0.0, self._dwell_remaining_s - dt_sim_seconds)

    def maybe_switch(self, bus_voltage: float, dt_sim_seconds: float) -> bool:
        self.tick_dwell(dt_sim_seconds)
        if self._dwell_remaining_s > 0.0:
            return False

        if bus_voltage < TAP_DEADBAND_LOW_PU and self.step < self.n_steps:
            self.step += 1
            self._dwell_remaining_s = TAP_DWELL_S
            return True
        if bus_voltage > TAP_DEADBAND_HIGH_PU and self.step > -self.n_steps:
            self.step -= 1
            self._dwell_remaining_s = TAP_DWELL_S
            return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MANUAL SVC / STATCOM
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SVC:
    """
    Manual continuous static VAR compensator at a bus. Player-set MVAr
    setpoint via GridSimulation.set_svc_setpoint() — not automatic.
    """
    bus: BusLabel
    q_setpoint_mvar: float = 0.0
    q_min_mvar: float = SVC_Q_MIN_MVAR
    q_max_mvar: float = SVC_Q_MAX_MVAR

    def set_setpoint(self, q_mvar: float) -> None:
        self.q_setpoint_mvar = max(self.q_min_mvar, min(self.q_max_mvar, float(q_mvar)))


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class ReactiveDevices:
    """
    Owns all reactive compensation devices for a shift and exposes their
    combined Q injection per bus. Automatic devices (shunts, taps) are
    stepped once per tick via step_automatics(); the manual SVC is set
    directly by the player.

    Usage:
        devices = ReactiveDevices()
        devices.add_shunt_bank(ShuntBank(bus='WEAK'))
        devices.add_svc(SVC(bus='WEAK'))
        # Each tick, before building Q injections:
        devices.step_automatics(prev_bus_voltages, dt_sim_seconds)
        q = devices.q_injections()
    """

    def __init__(self) -> None:
        self._shunt_banks: dict[BusLabel, ShuntBank] = {}
        self._taps: dict[str, TransformerTap] = {}
        self._svcs: dict[BusLabel, SVC] = {}

    # ─────── REGISTRATION ──────────────────────────────────────────────────

    def add_shunt_bank(self, bank: ShuntBank) -> None:
        self._shunt_banks[bank.bus] = bank

    def add_tap(self, tap: TransformerTap) -> None:
        self._taps[tap.label] = tap

    def add_svc(self, svc: SVC) -> None:
        self._svcs[svc.bus] = svc

    def has_svc(self, bus: BusLabel) -> bool:
        return bus in self._svcs

    # ─────── AUTOMATIC CONTROL ─────────────────────────────────────────────

    def step_automatics(self, bus_voltages: dict[BusLabel, float], dt_sim_seconds: float) -> None:
        """
        Step every automatic shunt bank and tap toward its deadband, based
        on the previous tick's solved voltage at its regulated bus (one-tick
        lag — called before the current tick's Q injections are built, so
        there is no algebraic loop with the solver). Deadband + hysteresis +
        minimum dwell time (all in constants.py) prevent step-hunting.
        """
        for bank in self._shunt_banks.values():
            v = bus_voltages.get(bank.bus)
            if v is not None:
                bank.maybe_switch(v, dt_sim_seconds)

        for tap in self._taps.values():
            v = bus_voltages.get(tap.regulated_bus)
            if v is not None:
                tap.maybe_switch(v, dt_sim_seconds)

    # ─────── MANUAL CONTROL ────────────────────────────────────────────────

    def set_svc_setpoint(self, bus: BusLabel, q_mvar: float) -> bool:
        svc = self._svcs.get(bus)
        if svc is None:
            return False
        svc.set_setpoint(q_mvar)
        return True

    # ─────── Q INJECTIONS ──────────────────────────────────────────────────

    def q_injections(self, tap_q_mvar: dict[BusLabel, float] | None = None) -> dict[BusLabel, float]:
        """
        Combined Q injection per bus from all devices.

        Args:
            tap_q_mvar: {regulated_bus: q_mvar} precomputed by the caller
                        (GridSimulation) from each tap's delta_v_pu via
                        VoltageModel.b_diag() — taps don't know S_BASE/B'
                        themselves, so the caller supplies the converted MVAr.
        """
        q: dict[BusLabel, float] = {}
        for bank in self._shunt_banks.values():
            q[bank.bus] = q.get(bank.bus, 0.0) + bank.mvar
        for svc in self._svcs.values():
            q[svc.bus] = q.get(svc.bus, 0.0) + svc.q_setpoint_mvar
        if tap_q_mvar:
            for bus, mvar in tap_q_mvar.items():
                q[bus] = q.get(bus, 0.0) + mvar
        return q

    # ─────── STATE SNAPSHOT ────────────────────────────────────────────────

    def get_shunt_state(self) -> dict[BusLabel, tuple[int, float]]:
        """{bus_label: (step, mvar)} for every automatic shunt bank."""
        return {bus: (bank.step, bank.mvar) for bus, bank in self._shunt_banks.items()}

    def get_tap_state(self) -> dict[str, tuple[BusLabel, int]]:
        """{tap_label: (regulated_bus, step)} for every automatic tap."""
        return {lbl: (tap.regulated_bus, tap.step) for lbl, tap in self._taps.items()}

    def get_svc_state(self) -> dict[BusLabel, tuple[float, float, float]]:
        """{bus_label: (q_setpoint_mvar, q_min_mvar, q_max_mvar)} for every SVC."""
        return {
            bus: (svc.q_setpoint_mvar, svc.q_min_mvar, svc.q_max_mvar)
            for bus, svc in self._svcs.items()
        }

    def tap_delta_v(self) -> dict[str, tuple[BusLabel, float]]:
        """{tap_label: (regulated_bus, delta_v_pu)} — used by the caller to
        convert each tap's voltage correction into a Q injection via
        VoltageModel.b_diag()."""
        return {lbl: (tap.regulated_bus, tap.delta_v_pu) for lbl, tap in self._taps.items()}
