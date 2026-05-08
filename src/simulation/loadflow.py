"""
src/simulation/loadflow.py

DC load flow solver for the GRIDCOM transmission network.
Solves the linear system θ = B⁻¹ × P using numpy.
Provides bus voltage angles, line flows (MW), and line loading percentages.

See GRID_SIMULATION_MECHANICS.md Section 4 for physics detail.
See SIMULATION_API.md for the public interface contract.
See DOMAIN_GLOSSARY.md — "The DC Load Flow (GRIDCOM Specific)" for definitions.
"""

import numpy as np

from simulation.constants import S_BASE, YSHUNT_REG, DEBUG_SIMULATION
from simulation.grid import Grid

# Type aliases
BusLabel    = str       # 4-char bus identifier: 'MDBY', 'CNTR'
LineLabel   = str       # line identifier: 'L01', 'L02'
PowerMW     = float     # active power in MW
AngleRad    = float     # bus voltage angle in radians
LoadingPct  = float     # 0.0 to 200.0+ (percent of thermal rating)


class DCLoadFlow:
    """
    DC load flow solver for the GRIDCOM transmission network.

    Solves the linear system θ = B⁻¹ × P where B is the network
    susceptance matrix and P is the net power injection vector.

    The slack bus (MDBY) provides the angle reference (θ = 0) and
    absorbs system imbalance. Its row/column is removed before solving.

    All internal calculations use per-unit on S_BASE = 1000 MVA.
    Inputs and outputs are in real MW; conversion is handled internally.

    Attributes:
        grid:       The Grid object this solver was built from.
        slack_bus:  Label of the slack bus (always 'MDBY').

    Usage:
        lf = DCLoadFlow(grid)
        p_injections = {'MDBY': 600.0, 'ASHF': -800.0, ...}  # MW
        result = lf.solve(p_injections)
        angles  = result.bus_angles      # {label: radians}
        flows   = result.line_flows_mw   # {label: MW}
        loading = result.line_loading_pct  # {label: %}
    """

    def __init__(self, grid: Grid) -> None:
        """
        Build the susceptance matrix from the grid's active lines.

        Args:
            grid: Loaded Grid object. Must have at least one active bus
                  and one active line.
        """
        self.grid = grid
        self.slack_bus: BusLabel = grid.slack_bus

        buses = grid.get_active_buses()
        self._bus_labels: list[BusLabel] = [b.label for b in buses]
        self._bus_index: dict[BusLabel, int] = {
            b.label: i for i, b in enumerate(buses)
        }

        self._active_lines = grid.get_active_lines()
        self._b_full: np.ndarray = self._build_b_matrix()
        self._b_reduced, self._reduced_index, self._mask = self._reduce_b_matrix()

        # Cache line data for fast flow computation
        lines = self._active_lines
        self._line_labels:    list[LineLabel] = [l.label for l in lines]
        self._line_from_idx:  list[int]       = [self._bus_index[l.from_bus] for l in lines]
        self._line_to_idx:    list[int]       = [self._bus_index[l.to_bus]   for l in lines]
        self._line_b:         np.ndarray      = np.array(
            [1.0 / l.reactance_pu for l in lines], dtype=np.float64
        )
        self._line_ratings:   np.ndarray      = np.array(
            [l.rating_mw for l in lines], dtype=np.float64
        )

    # ─────── B MATRIX CONSTRUCTION ────────────────────────────────────────

    def _build_b_matrix(self) -> np.ndarray:
        """
        Build the full n×n susceptance matrix.

        B[i,i] = sum of (1/X) for all lines connected to bus i, plus YSHUNT_REG
        B[i,j] = -(1/X) for each line between bus i and bus j
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

        # Add shunt regularisation to diagonal for numerical stability
        for k in range(n):
            b[k, k] += YSHUNT_REG

        return b

    def _reduce_b_matrix(self) -> tuple[np.ndarray, dict[BusLabel, int], np.ndarray]:
        """
        Remove the slack bus row and column to form the reduced (n-1)×(n-1) matrix.

        Returns:
            b_reduced:     (n-1)×(n-1) numpy array.
            reduced_index: Maps non-slack bus labels to their reduced matrix index.
            mask:          Boolean mask — True for non-slack buses.
        """
        n = len(self._bus_labels)
        slack_idx = self._bus_index[self.slack_bus]

        mask = np.ones(n, dtype=bool)
        mask[slack_idx] = False

        b_reduced = self._b_full[np.ix_(mask, mask)]

        reduced_index: dict[BusLabel, int] = {}
        r = 0
        for label in self._bus_labels:
            if label != self.slack_bus:
                reduced_index[label] = r
                r += 1

        return b_reduced, reduced_index, mask

    # ─────── SOLVER ───────────────────────────────────────────────────────

    def solve(
        self,
        p_injections: dict[BusLabel, PowerMW]
    ) -> 'LoadFlowResult':
        """
        Solve for bus voltage angles and compute line flows.

        Args:
            p_injections: Net MW injection at each active bus.
                          Positive = net generation. Negative = net load.
                          Must include all active buses. The slack bus entry
                          is accepted but ignored (slack absorbs imbalance).

        Returns:
            LoadFlowResult with bus_angles, line_flows_mw, line_loading_pct.

        Side effects:
            None. Pure function — does not modify instance state.
        """
        p_vector = self._build_p_vector(p_injections)

        try:
            theta_reduced = np.linalg.solve(self._b_reduced, p_vector)
        except np.linalg.LinAlgError:
            # Singular matrix — network is islanded or disconnected.
            # Return zero angles; caller must check island state.
            if DEBUG_SIMULATION:
                print('[LOADFLOW] WARNING: singular B matrix — returning zero angles')
            theta_reduced = np.zeros(len(p_vector), dtype=np.float64)

        theta_full = self._expand_theta(theta_reduced)
        bus_angles = self._theta_to_dict(theta_full)
        line_flows_mw, line_loading_pct = self._compute_line_flows(theta_full)

        return LoadFlowResult(
            bus_angles=bus_angles,
            line_flows_mw=line_flows_mw,
            line_loading_pct=line_loading_pct,
        )

    # ─────── HELPERS ──────────────────────────────────────────────────────

    def _build_p_vector(
        self,
        p_injections: dict[BusLabel, PowerMW]
    ) -> np.ndarray:
        """Build the reduced per-unit injection vector (slack bus excluded)."""
        n_reduced = len(self._reduced_index)
        p = np.zeros(n_reduced, dtype=np.float64)
        for label, mw in p_injections.items():
            if label == self.slack_bus:
                continue
            idx = self._reduced_index.get(label)
            if idx is not None:
                p[idx] = mw / S_BASE
        return p

    def _expand_theta(self, theta_reduced: np.ndarray) -> np.ndarray:
        """Insert slack bus angle (0.0) back into the full angle vector."""
        n = len(self._bus_labels)
        theta_full = np.zeros(n, dtype=np.float64)
        r = 0
        slack_idx = self._bus_index[self.slack_bus]
        for k in range(n):
            if k == slack_idx:
                theta_full[k] = 0.0
            else:
                theta_full[k] = theta_reduced[r]
                r += 1
        return theta_full

    def _theta_to_dict(
        self,
        theta_full: np.ndarray
    ) -> dict[BusLabel, AngleRad]:
        """Convert full angle array to {bus_label: angle_rad} dict."""
        return {
            label: float(theta_full[i])
            for label, i in self._bus_index.items()
        }

    def _compute_line_flows(
        self,
        theta_full: np.ndarray
    ) -> tuple[dict[LineLabel, PowerMW], dict[LineLabel, LoadingPct]]:
        """
        Compute MW flow and loading percentage for each active line.

        P_line(i→j) = (θᵢ - θⱼ) / Xᵢⱼ  [per-unit]
        P_line_mw   = P_line_pu × S_BASE
        loading_pct = |P_line_mw| / rating_mw × 100
        """
        theta_from = theta_full[self._line_from_idx]
        theta_to   = theta_full[self._line_to_idx]
        flows_pu   = (theta_from - theta_to) * self._line_b
        flows_mw   = flows_pu * S_BASE

        line_flows_mw:    dict[LineLabel, PowerMW]    = {}
        line_loading_pct: dict[LineLabel, LoadingPct] = {}

        for k, label in enumerate(self._line_labels):
            flow = float(flows_mw[k])
            loading = abs(flow) / self._line_ratings[k] * 100.0
            line_flows_mw[label]    = flow
            line_loading_pct[label] = loading

        return line_flows_mw, line_loading_pct

    # ─────── REBUILD ──────────────────────────────────────────────────────

    def rebuild(self, lines_in_service: list | None = None) -> None:
        """
        Rebuild the B matrix and cached line data.

        Call this after any topology change (line trip or close) before
        calling solve() again.

        Args:
            lines_in_service: Filtered line list (in-service only). If None,
                              uses all active lines from the grid.
        """
        if lines_in_service is not None:
            self._active_lines = lines_in_service
        else:
            self._active_lines = self.grid.get_active_lines()

        self._b_full = self._build_b_matrix()
        self._b_reduced, self._reduced_index, self._mask = self._reduce_b_matrix()

        lines = self._active_lines
        self._line_labels   = [l.label for l in lines]
        self._line_from_idx = [self._bus_index[l.from_bus] for l in lines]
        self._line_to_idx   = [self._bus_index[l.to_bus]   for l in lines]
        self._line_b        = np.array(
            [1.0 / l.reactance_pu for l in lines], dtype=np.float64
        )
        self._line_ratings  = np.array(
            [l.rating_mw for l in lines], dtype=np.float64
        )


class LoadFlowResult:
    """
    Result of a DC load flow solve.

    Attributes:
        bus_angles:        {bus_label: angle_rad} for all active buses.
                           Slack bus (MDBY) = 0.0 always.
        line_flows_mw:     {line_label: flow_mw}
                           Positive: from_bus → to_bus. Negative: reverse.
        line_loading_pct:  {line_label: loading_pct}
                           |flow_mw| / rating_mw × 100. 100+ = overloaded.
    """

    __slots__ = ('bus_angles', 'line_flows_mw', 'line_loading_pct')

    def __init__(
        self,
        bus_angles:       dict[BusLabel, AngleRad],
        line_flows_mw:    dict[LineLabel, PowerMW],
        line_loading_pct: dict[LineLabel, LoadingPct],
    ) -> None:
        self.bus_angles:       dict[BusLabel, AngleRad]    = bus_angles
        self.line_flows_mw:    dict[LineLabel, PowerMW]    = line_flows_mw
        self.line_loading_pct: dict[LineLabel, LoadingPct] = line_loading_pct
