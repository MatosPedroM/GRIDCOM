"""
src/simulation/cascade.py

Cascade detection and island finding for the GRIDCOM simulation.

CascadeModel is stateless — all state (overload timers, island list,
blackout zones) lives in GridSimulation. The caller passes current
grid topology and line loading each tick; this module computes results
and returns them.

Two responsibilities:
  1. Island finding — BFS connected components from active buses and
     in-service lines. Used every tick after any topology change.
  2. Overload protection — accumulates per-line overload timers and
     returns trip signals when TRIP_DELAY_S is exceeded.

See GRID_SIMULATION_MECHANICS.md — cascade sequence for tick ordering.
See SIMULATION_API.md — SimulationState.islands / blackout_zones.
"""

from collections import deque

from simulation.constants import TRIP_DELAY_S, OVERLOAD_CRIT_PCT


class CascadeModel:
    """
    Stateless cascade detector and island finder.

    All methods are pure functions of their arguments — no internal
    state is mutated between calls. The caller (GridSimulation) owns
    the overload_timers dict and passes it in each tick.
    """

    # ─────── ISLAND FINDING ───────────────────────────────────────────────

    def find_islands(
        self,
        buses: list,
        lines_in_service: list,
    ) -> list:
        """
        Find all connected islands in the current network topology.

        Uses BFS from each unvisited bus across in-service lines only.
        Tripped lines are excluded by the caller before passing.

        Args:
            buses:             list[Bus] — all active buses.
            lines_in_service:  list[Line] — lines currently in service.

        Returns:
            list[frozenset[str]] — each frozenset contains bus labels
            in one connected island. Normal (no trips): length 1.
            Single isolated bus: its own frozenset of length 1.
        """
        adjacency = self._build_adjacency(buses, lines_in_service)
        visited: set[str] = set()
        islands: list[frozenset] = []

        for bus in buses:
            if bus.label not in visited:
                island = self._bfs(bus.label, adjacency)
                islands.append(frozenset(island))
                visited.update(island)

        return islands

    def check_island_viability(
        self,
        island: frozenset,
        active_generation_buses: frozenset,
    ) -> bool:
        """
        Determine whether an island can sustain itself.

        An island is viable if it contains at least one bus with an ONLINE
        or SHUTDOWN generation unit. OFFLINE and STARTING units do not count.

        Args:
            island:                   frozenset[str] — bus labels in this island.
            active_generation_buses:  frozenset[str] — buses with at least one
                                      ONLINE or SHUTDOWN unit. Computed by caller
                                      via GridSimulation._get_active_generation_buses().

        Returns:
            True if viable (has active generation), False otherwise.
        """
        return bool(island & active_generation_buses)

    def get_blackout_zones(
        self,
        islands: list,
        active_generation_buses: frozenset,
    ) -> frozenset:
        """
        Return the set of bus labels in all non-viable islands.

        Args:
            islands:                  list[frozenset[str]] from find_islands().
            active_generation_buses:  frozenset[str] — passed to
                                      check_island_viability().

        Returns:
            frozenset[str] — all bus labels currently blacked out.
        """
        blackout: set[str] = set()
        for island in islands:
            if not self.check_island_viability(island, active_generation_buses):
                blackout.update(island)
        return frozenset(blackout)

    # ─────── OVERLOAD PROTECTION ──────────────────────────────────────────

    def check_overloads(
        self,
        loading_pct: dict,
        overload_timers: dict,
        dt_seconds: float,
    ) -> tuple:
        """
        Update overload timers and return lines that have exceeded TRIP_DELAY_S.

        Lines above OVERLOAD_CRIT_PCT (100%) accumulate time in their timer.
        Lines that fall back below 100% have their timer reset to 0.
        Lines whose timer exceeds TRIP_DELAY_S are returned for tripping.

        Args:
            loading_pct:      {line_label: loading_%} from load flow solver.
            overload_timers:  {line_label: elapsed_s} — caller's timer dict.
            dt_seconds:       Simulation time elapsed this tick (seconds).

        Returns:
            (lines_to_trip: list[str], updated_timers: dict[str, float])
            The caller replaces its timer dict with updated_timers.
        """
        updated: dict[str, float] = {}
        lines_to_trip: list[str] = []

        for line_label, loading in loading_pct.items():
            if loading >= OVERLOAD_CRIT_PCT:
                elapsed = overload_timers.get(line_label, 0.0) + dt_seconds
                if elapsed > TRIP_DELAY_S:
                    lines_to_trip.append(line_label)
                    # Timer cleared after trip — no re-trip on same line
                    updated[line_label] = 0.0
                else:
                    updated[line_label] = elapsed
            else:
                # Below threshold — reset timer
                updated[line_label] = 0.0

        return lines_to_trip, updated

    # ─────── PRIVATE HELPERS ──────────────────────────────────────────────

    def _build_adjacency(self, buses: list, lines_in_service: list) -> dict:
        """
        Build undirected adjacency map from in-service lines.

        Returns:
            {bus_label: [neighbour_label, ...]}
        """
        adjacency: dict[str, list] = {bus.label: [] for bus in buses}
        for line in lines_in_service:
            if line.from_bus in adjacency and line.to_bus in adjacency:
                adjacency[line.from_bus].append(line.to_bus)
                adjacency[line.to_bus].append(line.from_bus)
        return adjacency

    def _bfs(self, start: str, adjacency: dict) -> set:
        """
        Breadth-first search from start node.

        Returns:
            set[str] — all bus labels reachable from start.
        """
        visited: set[str] = {start}
        queue: deque[str] = deque([start])
        while queue:
            node = queue.popleft()
            for neighbour in adjacency.get(node, []):
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(neighbour)
        return visited
