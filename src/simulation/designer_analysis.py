"""
src/simulation/designer_analysis.py

Static power-flow analysis for the Grid Designer: a one-shot DC load flow
plus N-1 contingency sweep against a designer-built topology. No ticking,
no ramping — dispatch MW / load MW / line service state are supplied
directly by the caller for a single solve.

Composes the existing DCLoadFlow (simulation/loadflow.py) and CascadeModel
(simulation/cascade.py) against anything satisfying the Grid duck-type
(DesignerGrid, or the real Grid class). No new solver math is introduced.

See STAGE_STATUS.md Sessions 35/36 for the hand-rolled version of this
methodology (static dispatch -> P-injections -> DCLoadFlow.rebuild() per
contingency) that this module formalizes into reusable functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from simulation.loadflow import DCLoadFlow
from simulation.cascade import CascadeModel
from config.constants import DESIGNER_N1_OVERLOAD_PCT


@dataclass
class LineFlowResult:
    label:       str
    loading_pct: float
    flow_mw:     float
    in_service:  bool


@dataclass
class N1ContingencyResult:
    tripped_line:      str
    worst_loading_pct: float
    worst_line_label:  str | None
    blackout_buses:    frozenset[str]
    passed:            bool


@dataclass
class AnalysisResult:
    line_flows:               dict[str, LineFlowResult]
    total_dispatched_mw:      float
    total_available_mw:       float
    total_load_mw:            float
    slack_vs_load_mw:         float
    headroom_vs_installed_mw: float
    n1_results:               list[N1ContingencyResult] = field(default_factory=list)
    n1_worst_pct:             float = 0.0
    n1_all_passed:            bool = True
    solver_error:             str | None = None


def build_p_injections(
    grid,
    unit_mw: dict[str, float],
    unit_available: dict[str, bool],
    bus_load_mw: dict[str, float],
) -> dict[str, float]:
    """
    Net MW injection per active bus: sum of dispatched MW for available
    units at that bus, minus the override load MW for LOAD buses.

    Units absent from unit_mw/unit_available, or with unit_available=False,
    contribute 0 (excluded, matching "unavailable" semantics). Buses absent
    from bus_load_mw contribute 0 load.
    """
    p: dict[str, float] = {b.label: 0.0 for b in grid.get_active_buses()}
    for unit in grid.get_active_units():
        if not unit_available.get(unit.label, True):
            continue
        mw = unit_mw.get(unit.label, 0.0)
        p[unit.bus_label] = p.get(unit.bus_label, 0.0) + mw
    for bus in grid.get_active_buses():
        if bus.bus_type == 'LOAD':
            p[bus.label] = p.get(bus.label, 0.0) - bus_load_mw.get(bus.label, 0.0)
    return p


def run_static_solve(
    grid,
    unit_mw: dict[str, float],
    unit_available: dict[str, bool],
    bus_load_mw: dict[str, float],
    line_in_service: dict[str, bool],
) -> tuple[dict[str, LineFlowResult], str | None]:
    """
    Solve one DC load flow at the given dispatch/load/line-service state.

    Returns (line_flows, error). Never raises — solver failures (e.g. a
    singular matrix from an islanded slack bus) are caught and surfaced as
    the error string, with line_flows reflecting whatever DCLoadFlow.solve()
    returned (zero-angle fallback) so callers can still render something.
    """
    in_service_lines = [
        l for l in grid.get_active_lines()
        if line_in_service.get(l.label, True)
    ]
    p_inj = build_p_injections(grid, unit_mw, unit_available, bus_load_mw)
    error: str | None = None
    line_flows: dict[str, LineFlowResult] = {}
    try:
        lf = DCLoadFlow(grid)
        lf.rebuild(lines_in_service=in_service_lines)
        result = lf.solve(p_inj)
        for line in grid.get_active_lines():
            in_svc = line_in_service.get(line.label, True)
            if line.label in result.line_loading_pct:
                line_flows[line.label] = LineFlowResult(
                    label=line.label,
                    loading_pct=result.line_loading_pct[line.label],
                    flow_mw=result.line_flows_mw[line.label],
                    in_service=in_svc,
                )
            else:
                line_flows[line.label] = LineFlowResult(
                    label=line.label, loading_pct=0.0, flow_mw=0.0, in_service=in_svc,
                )
    except Exception as exc:  # noqa: BLE001 — surfaced to caller, never raised
        error = str(exc)
    return line_flows, error


def run_n1_sweep(
    grid,
    unit_mw: dict[str, float],
    unit_available: dict[str, bool],
    bus_load_mw: dict[str, float],
    line_in_service: dict[str, bool],
) -> list[N1ContingencyResult]:
    """
    Trip each in-service line alone (one at a time), re-solve, and report
    the worst-case loading and any resulting island/blackout.

    Reuses one DCLoadFlow instance across the whole sweep via repeated
    rebuild() calls, per the Session 35/36-documented methodology. Restores
    the solver to the full in-service line set before returning.
    """
    p_inj = build_p_injections(grid, unit_mw, unit_available, bus_load_mw)
    base_in_service = [
        l for l in grid.get_active_lines()
        if line_in_service.get(l.label, True)
    ]
    if not base_in_service:
        return []

    cascade = CascadeModel()
    active_gen_buses = frozenset(
        u.bus_label for u in grid.get_active_units()
        if unit_available.get(u.label, True) and unit_mw.get(u.label, 0.0) > 0.0
    )

    lf = DCLoadFlow(grid)
    results: list[N1ContingencyResult] = []

    for tripped in base_in_service:
        reduced = [l for l in base_in_service if l.label != tripped.label]

        islands = cascade.find_islands(grid.get_active_buses(), reduced)
        blackout = cascade.get_blackout_zones(islands, active_gen_buses)

        try:
            lf.rebuild(lines_in_service=reduced)
            result = lf.solve(p_inj)
            worst_pct = 0.0
            worst_label: str | None = None
            for label, pct in result.line_loading_pct.items():
                if pct > worst_pct:
                    worst_pct = pct
                    worst_label = label
        except Exception:  # noqa: BLE001 — treat as a failed/unsafe contingency
            worst_pct = float('inf')
            worst_label = None

        passed = worst_pct <= DESIGNER_N1_OVERLOAD_PCT and not blackout
        results.append(N1ContingencyResult(
            tripped_line=tripped.label,
            worst_loading_pct=worst_pct,
            worst_line_label=worst_label,
            blackout_buses=blackout,
            passed=passed,
        ))

    # Restore the solver to the full in-service set so a caller reusing it
    # afterward isn't left mid-contingency.
    lf.rebuild(lines_in_service=base_in_service)

    return results


def run_full_analysis(
    grid,
    unit_mw: dict[str, float],
    unit_available: dict[str, bool],
    bus_load_mw: dict[str, float],
    line_in_service: dict[str, bool],
) -> AnalysisResult:
    """Top-level entry point: base-case solve + N-1 sweep + balance summary."""
    line_flows, error = run_static_solve(
        grid, unit_mw, unit_available, bus_load_mw, line_in_service)

    total_dispatched_mw = sum(
        unit_mw.get(u.label, 0.0)
        for u in grid.get_active_units()
        if unit_available.get(u.label, True)
    )
    total_available_mw = sum(
        u.rated_mw for u in grid.get_active_units()
        if unit_available.get(u.label, True)
    )
    total_load_mw = sum(
        bus_load_mw.get(b.label, 0.0)
        for b in grid.get_active_buses()
        if b.bus_type == 'LOAD'
    )

    n1_results = run_n1_sweep(
        grid, unit_mw, unit_available, bus_load_mw, line_in_service)
    n1_worst_pct = max((r.worst_loading_pct for r in n1_results), default=0.0)
    n1_all_passed = all(r.passed for r in n1_results)

    return AnalysisResult(
        line_flows=line_flows,
        total_dispatched_mw=total_dispatched_mw,
        total_available_mw=total_available_mw,
        total_load_mw=total_load_mw,
        slack_vs_load_mw=total_dispatched_mw - total_load_mw,
        headroom_vs_installed_mw=total_available_mw - total_dispatched_mw,
        n1_results=n1_results,
        n1_worst_pct=n1_worst_pct,
        n1_all_passed=n1_all_passed,
        solver_error=error,
    )
