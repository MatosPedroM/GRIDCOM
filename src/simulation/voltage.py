"""
src/simulation/voltage.py

Decoupled voltage model for the GRIDCOM transmission network.

Solves the linear system:
    ΔV = B'⁻¹ × Q

Where:
    B'     = reactive susceptance matrix (same structure as DC load flow B,
             but built from susceptances, not reactances — in practice identical
             for lossless lines: B'[i,j] = -b_ij = -1/x_ij)
    Q      = net reactive injection vector (MVAr / S_BASE, per-unit)
    ΔV     = voltage deviation from nominal (per-unit)

Bus voltages: V[i] = 1.0 + ΔV[i]

PV buses (generators with reactive control) maintain a target voltage by
adjusting Q injection. When Q hits the unit limit the bus converts to PQ
(constant Q) — this is the PV→PQ conversion.

Voltage is NOT clamped here — the cascade module checks thresholds and
acts on the result. V_CRITICAL_LOW blackout and V_WARNING_LOW acceleration
are applied by the caller.

See DOMAIN_GLOSSARY.md — "Decoupled Voltage Model" for definitions.
See GRID_SIMULATION_MECHANICS.md Section 6 for physics detail.
"""

import logging

import numpy as np

from config.constants import (
    S_BASE,
    VSHUNT_REG,
    PV_CORRECTION_MAX_ITERS,
    PV_CORRECTION_Q_TOL_MVAR,
    DEBUG_SIMULATION,
)
from simulation.designer_grid import DesignerGrid

# Type aliases
BusLabel    = str
PowerMVAr   = float
VoltagePU   = float


class VoltageModel:
    """
    Decoupled voltage model: ΔV = B'⁻¹ × Q.

    The B' matrix structure mirrors the DC load flow B matrix but represents
    the reactive susceptance coupling. For the lossless approximation used
    in GRIDCOM, B'[i,j] = -(1/x_ij) exactly as in the DC load flow.

    PV buses hold voltage by absorbing/injecting reactive power within limits.
    When a PV bus hits its Q limit it is converted to PQ for that solve.

    Attributes:
        grid:  The DesignerGrid object this model was built from.

    Usage:
        vm = VoltageModel(grid)
        q_injections = {'MDBY': 200.0, 'HART': -100.0, ...}  # MVAr
        pv_buses = {'MDBY': (1.03, 400.0, -200.0), ...}  # label: (V_target, Q_max, Q_min)
        result = vm.solve(q_injections, pv_buses)
        voltages = result.bus_voltages     # {label: pu}
        pq_conversions = result.pq_buses   # set of labels that hit Q limit
    """

    def __init__(self, grid: DesignerGrid) -> None:
        """
        Build the reactive susceptance matrix from the grid's active lines.

        Args:
            grid: Loaded DesignerGrid object. Must have at least one active
                  bus and one active line.
        """
        self.grid = grid
        self._slack_bus: BusLabel = grid.slack_bus

        buses = grid.get_active_buses()
        self._bus_labels: list[BusLabel] = [b.label for b in buses]
        self._bus_index: dict[BusLabel, int] = {
            b.label: i for i, b in enumerate(buses)
        }

        self._active_lines = grid.get_active_lines()
        self._b_prime: np.ndarray = self._build_b_prime()
        self._b_reduced, self._reduced_index, self._mask = self._reduce_b_prime()

    # ─────── B' MATRIX CONSTRUCTION ──────────────────────────────────────

    def _build_b_prime(self) -> np.ndarray:
        """
        Build the full n×n reactive susceptance matrix.

        B'[i,i] = sum of (1/X) for all lines connected to bus i, plus YSHUNT_REG
        B'[i,j] = -(1/X) for each line between bus i and bus j

        Identical structure to the DC load flow B matrix.
        """
        n = len(self._bus_labels)
        b = np.zeros((n, n), dtype=np.float64)

        for line in self._active_lines:
            i = self._bus_index[line.from_bus]
            j = self._bus_index[line.to_bus]
            b_ij = 1.0 / line.reactance_pu
            b[i, i] += b_ij
            b[j, j] += b_ij
            b[i, j] -= b_ij
            b[j, i] -= b_ij

        for k in range(n):
            b[k, k] += VSHUNT_REG

        return b

    def _reduce_b_prime(self) -> tuple[np.ndarray, dict[BusLabel, int], np.ndarray]:
        """
        Remove the slack bus row and column from B' to form the (n-1)×(n-1) matrix.

        The slack bus holds V = 1.0 always (angle and voltage reference).

        Returns:
            b_reduced:     (n-1)×(n-1) numpy array.
            reduced_index: Maps non-slack bus labels to their reduced index.
            mask:          Boolean mask — True for non-slack buses.
        """
        n = len(self._bus_labels)
        slack_idx = self._bus_index[self._slack_bus]

        mask = np.ones(n, dtype=bool)
        mask[slack_idx] = False

        b_reduced = self._b_prime[np.ix_(mask, mask)]

        reduced_index: dict[BusLabel, int] = {}
        r = 0
        for label in self._bus_labels:
            if label != self._slack_bus:
                reduced_index[label] = r
                r += 1

        return b_reduced, reduced_index, mask

    # ─────── SOLVER ───────────────────────────────────────────────────────

    def solve(
        self,
        q_injections: dict[BusLabel, PowerMVAr],
        pv_buses: dict[BusLabel, tuple[float, float, float]] | None = None,
    ) -> 'VoltageResult':
        """
        Solve for bus voltage magnitudes.

        Args:
            q_injections: Net MVAr injection at each active bus.
                          Positive = reactive injection (capacitive / generator lagging).
                          Negative = reactive absorption (inductive / generator leading).
                          Must include all active buses. Slack bus entry is ignored.
            pv_buses:     Optional dict of PV bus constraints.
                          {bus_label: (v_target_pu, q_max_mvar, q_min_mvar)}
                          PV buses will have their Q adjusted to maintain v_target_pu
                          within [q_min_mvar, q_max_mvar]. Buses that hit a Q limit
                          are converted to PQ for this solve.

        Returns:
            VoltageResult with bus_voltages and pq_buses.

        Side effects:
            None. Pure function — does not modify instance state.
        """
        pv_buses = pv_buses or {}

        # First pass: solve with supplied Q injections.
        q_injections_working = dict(q_injections)
        pq_conversions: set[BusLabel] = set()

        # PV bus correction: adjust each PV bus's Q to hit its target voltage,
        # then re-solve. A single pass is only adequate when every PV bus has
        # one dominant electrical path; buses with two comparable paths (or
        # one weak/remote path) need this iterated to a fixed point, or Q
        # re-chases the same error every tick and the bus can diverge. Iterate
        # to a bounded fixed point: stop once the largest per-pass Q change is
        # small (the bus is satisfied, with real reserve left), or after a
        # hard cap so a pathological grid can never hang the tick.
        if pv_buses:
            for _ in range(PV_CORRECTION_MAX_ITERS):
                delta_v = self._solve_delta_v(q_injections_working)
                max_delta_q = 0.0

                for label, (v_target, q_max, q_min) in pv_buses.items():
                    if label == self._slack_bus:
                        continue
                    idx = self._reduced_index.get(label)
                    if idx is None:
                        continue
                    # PV→PQ is sticky within a solve: once a bus has hit its Q
                    # limit its Q is fixed there — don't pull it back off.
                    if label in pq_conversions:
                        continue

                    v_current = 1.0 + delta_v.get(label, 0.0)
                    v_error = v_target - v_current

                    # Q needed to correct voltage: ΔQ ≈ B'[i,i] × ΔV × S_BASE
                    full_idx = self._bus_index[label]
                    b_diag = self._b_prime[full_idx, full_idx]
                    delta_q_mvar = b_diag * v_error * S_BASE

                    q_current = q_injections_working.get(label, 0.0)
                    q_new = q_current + delta_q_mvar

                    # Clamp to reactive limits (converts PV→PQ at a limit).
                    if q_new > q_max:
                        q_new = q_max
                        pq_conversions.add(label)
                    elif q_new < q_min:
                        q_new = q_min
                        pq_conversions.add(label)

                    max_delta_q = max(max_delta_q, abs(q_new - q_current))
                    q_injections_working[label] = q_new

                # Converged: this pass barely moved any PV bus's Q.
                if max_delta_q < PV_CORRECTION_Q_TOL_MVAR:
                    break

        # Final solve with corrected Q values.
        delta_v_dict = self._solve_delta_v(q_injections_working)

        # Build voltage dict: slack = 1.0, others = 1.0 + ΔV.
        bus_voltages: dict[BusLabel, VoltagePU] = {}
        for label in self._bus_labels:
            if label == self._slack_bus:
                bus_voltages[label] = 1.0
            else:
                bus_voltages[label] = 1.0 + delta_v_dict.get(label, 0.0)

        return VoltageResult(
            bus_voltages=bus_voltages,
            pq_buses=pq_conversions,
            q_injections_used=q_injections_working,
        )

    # ─────── HELPERS ──────────────────────────────────────────────────────

    def _solve_delta_v(
        self,
        q_injections: dict[BusLabel, PowerMVAr],
    ) -> dict[BusLabel, float]:
        """
        Solve ΔV = B'⁻¹ × Q_pu for non-slack buses.

        Returns {bus_label: delta_v_pu} for all non-slack buses.
        """
        n_reduced = len(self._reduced_index)
        q_vec = np.zeros(n_reduced, dtype=np.float64)

        for label, mvar in q_injections.items():
            if label == self._slack_bus:
                continue
            idx = self._reduced_index.get(label)
            if idx is not None:
                q_vec[idx] = mvar / S_BASE

        try:
            delta_v = np.linalg.solve(self._b_reduced, q_vec)
        except np.linalg.LinAlgError:
            if DEBUG_SIMULATION:
                logging.getLogger('sim').debug('[VOLTAGE] WARNING: singular B\' matrix — returning zero ΔV')
            delta_v = np.zeros(n_reduced, dtype=np.float64)

        result: dict[BusLabel, float] = {}
        for label, idx in self._reduced_index.items():
            result[label] = float(delta_v[idx])

        return result

    # ─────── REBUILD ──────────────────────────────────────────────────────

    def rebuild(self, lines_in_service: list | None = None) -> None:
        """
        Rebuild B' matrix from the given in-service line list.

        Call after any line trip or close before the next solve.

        Args:
            lines_in_service: Filtered line list (in-service only). If None,
                              uses all active lines from the grid.
        """
        if lines_in_service is not None:
            self._active_lines = lines_in_service
        else:
            self._active_lines = self.grid.get_active_lines()
        self._b_prime = self._build_b_prime()
        self._b_reduced, self._reduced_index, self._mask = self._reduce_b_prime()


class VoltageResult:
    """
    Result of a voltage solve.

    Attributes:
        bus_voltages:       {bus_label: voltage_pu} for all active buses.
                            Slack bus (MDBY) = 1.0 always.
                            Healthy range: 0.95 to 1.05 pu.
        pq_buses:           Set of bus labels that hit a reactive limit and
                            were converted from PV to PQ for this solve.
        q_injections_used:  {bus_label: q_mvar} actual Q used in the solve.
                            May differ from input for PV buses that hit limits.
    """

    __slots__ = ('bus_voltages', 'pq_buses', 'q_injections_used')

    def __init__(
        self,
        bus_voltages: dict[BusLabel, VoltagePU],
        pq_buses: set[BusLabel],
        q_injections_used: dict[BusLabel, PowerMVAr],
    ) -> None:
        self.bus_voltages:      dict[BusLabel, VoltagePU]   = bus_voltages
        self.pq_buses:          set[BusLabel]               = pq_buses
        self.q_injections_used: dict[BusLabel, PowerMVAr]  = q_injections_used
