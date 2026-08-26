# DOMAIN_GLOSSARY.md — Power System Terminology for GRIDCOM
### Read this before working on any simulation module.
### These definitions describe GRIDCOM's simplified model, not real power systems.

---

## Critical Warning

GRIDCOM uses deliberate simplifications of real power system physics. Some terms
below mean something slightly different in GRIDCOM than in real power engineering.
The GRIDCOM definition is always the correct one for this codebase.
Do not "correct" the simulation toward real-world accuracy.

---

## Core Physical Quantities

**Active Power (MW)**
Real power — the component of power that does useful work. Measured in megawatts.
In GRIDCOM: all MW values are in real units (not per-unit) when stored in
SimulationState and when displayed to the player. Internally in the load flow
solver, MW is converted to per-unit by dividing by S_BASE (1000 MVA).

**Reactive Power (MVAr)**
Imaginary power — the component that maintains voltage levels. Measured in
megavolt-amperes reactive. Cannot be transported long distances — must be
produced close to where it is consumed. In GRIDCOM: solved by the decoupled
voltage model separately from active power.

**Per-Unit (pu)**
A normalised unit system where quantities are expressed as fractions of a
base value. In GRIDCOM: S_BASE = 1000 MVA. Voltage base = nominal voltage
at each bus (400kV, 220kV, 150kV, or 60kV). All internal matrix calculations
use per-unit. Display values are converted back to real units.

**Voltage (kV or pu)**
The electrical potential difference. In GRIDCOM:
- Transmission voltages: 400kV, 220kV, 150kV, 60kV
- In per-unit: 1.0 pu = nominal voltage at that bus
- Healthy operating range: 0.95 to 1.05 pu
- Below 0.85 pu: voltage collapse risk zone

**Frequency (Hz)**
The rate at which alternating current completes one cycle. Nominal = 50.0 Hz.
In GRIDCOM: frequency is a single system-wide value (not per-bus). It is the
primary indicator of generation-load balance. Deviation from 50 Hz means
the system is not balanced.

---

## Network Components

**Bus**
A node in the electrical network — a point where lines, generators, and loads
connect. In GRIDCOM: represented by a Bus dataclass with a 4-char label, voltage
level, type, and canvas position. There are 38 buses total (32 transmission + 6
load substations).

**Transmission Line**
An electrical conductor connecting two buses. In GRIDCOM: characterised by
reactance (pu), MW rating, and in-service status. Represented by a Line dataclass.
There are 29 lines in the full grid.

**Reactance (X, pu)**
The electrical resistance-like property of a line to alternating current flow.
In GRIDCOM: the primary parameter in the DC load flow. Higher X = more
resistance to power flow = weaker connection between buses.

**Substation**
A physical location where voltage is transformed and lines are connected.
In GRIDCOM: represented on the schematic as a square with triangle symbol.
Two types: transmission substations (upward triangle) and load substations
(downward triangle, 60kV, consumption only).

**Interconnector**
A transmission line connecting the fictional grid to an external system.
In GRIDCOM: INTC-N (North, ±800MW) and INTC-S (South, ±600MW). These are
external reference buses — they appear on the schematic but are not part of
the internal network topology. Their power flows are set by schedule, not
computed by the load flow.

---

## Bus Types (Load Flow)

**Slack Bus**
The reference bus — provides the voltage angle reference (θ = 0) and absorbs
the system power imbalance. In GRIDCOM: always MDBY (Midbury 400kV). The slack
bus row and column are removed from the B matrix before solving.

**PV Bus**
A bus where voltage magnitude is controlled (held at a setpoint) by a generator
with AVR (Automatic Voltage Regulator). The generator injects or absorbs reactive
power to maintain the voltage. In GRIDCOM: generator buses where the unit is ONLINE
and within its reactive limits.

**PQ Bus**
A bus where both active and reactive power injections are fixed. Voltage magnitude
is free to vary. In GRIDCOM: all load buses, and generator buses where the unit
has hit its reactive limits (PV → PQ conversion).

**PV → PQ Conversion**
When a generator at a PV bus hits its reactive capability limit (Q_max or Q_min),
it can no longer maintain voltage. The bus converts from PV to PQ. The generator's
reactive output is fixed at the limit, and the voltage is free to sag.
In GRIDCOM: maximum 2 passes of the voltage solver after conversion — no iterative loop.

---

## Generation

**Installed Capacity (MW)**
The maximum possible output of a generating unit at rated conditions.
In GRIDCOM: stored as `rated_mw` in the GenerationUnit dataclass.

**Dispatch (MW)**
The actual output instruction given to a unit. In GRIDCOM: the player sets
dispatch targets via context panel or autopilot. Units ramp toward their target
at their rated ramp rate.

**Ramp Rate (MW/min)**
The maximum rate at which a unit can change its output, expressed as an absolute
MW-per-simulated-minute value looked up by unit_type (constants.py's UNIT_DEFAULTS)
— not a percentage of that unit's own rated_mw, and not authored per-unit in grid
JSON. In GRIDCOM: enforced in UnitModel._tick_online()/_tick_shutdown().
Hydro: 250 MW/min (near-instant). Coal: 4.0 MW/min (slow). Nuclear: 3.5 MW/min
(very slow).

**Spinning Reserve (MW)**
Headroom available from online, synchronised units — the difference between their
current output and their rated output. In GRIDCOM: spinning reserve = Σ(rated_mw -
current_mw) for all ONLINE units. This is the buffer available for AGC's automatic
frequency response. Zero spinning reserve = no ability to respond to
frequency events.

**Inertia Constant H (seconds)**
A measure of how much rotational kinetic energy a generator stores relative to
its rated power. Higher H = more energy stored = slower frequency response to
imbalance. In GRIDCOM: system H is the generation-weighted average of all ONLINE
units. Solar and wind contribute zero inertia.

**Cold Start Time (simulated minutes)**
Time required for an OFFLINE unit to reach ONLINE status after a start command.
In GRIDCOM: unit enters STARTING state, counts down cold_start_min, then enters
ONLINE. During STARTING: contributes no power, no inertia, no AGC response.

---

## Generation Unit Types

**COAL**
Thermal unit burning coal. Slow ramp (4.0 MW/min). High inertia (H=5.0s).
High carbon cost. In GRIDCOM stations: RVSD (Riverside, 3×300MW, COALCOM easter egg),
THNF (Thornfield, 3×300MW). Both at 400kV.

**CCGT (Combined Cycle Gas Turbine)**
Gas-fired unit. Medium ramp (15.0 MW/min). Medium inertia (H=4.0s).
Gas price exposed. In GRIDCOM stations: ASHG (Ashford, 2×400MW),
WRNG (Wrentham, 2×400MW). Both at 220kV.

**NUCLEAR**
Baseload unit. Very slow ramp (3.5 MW/min). High inertia (H=6.0s).
Zero carbon. Always online (cannot be shut down by player in campaign).
In GRIDCOM: HART (Hartwell, 2×700MW, 400kV).

**HYDRO (reservoir, pumped storage)**
Reversible pump-turbine. Near-instant ramp (250 MW/min). Medium inertia (H=3.0s).
Can generate (source) or pump (sink). In GRIDCOM stations: BARR, KELM, DUNH
(upper reservoirs, 400kV). Has downstream lower plant.

**HYDRO (lower plant, downstream)**
Conventional turbine at base of penstock. Near-instant ramp.
Output depends on upstream reservoir release plus natural inflow.
In GRIDCOM stations: BARD, KELD, DUND (lower plants, 220kV).
Cannot pump — generate or idle only.

**HYDRO_ROR (run-of-river)**
Conventional hydro on river cascades. Near-instant ramp. Output depends on
river flow — partly weather-dependent. In GRIDCOM cascades: AR01-AR04 (River
Arden, 220kV), BR01-BR03 (River Brent, 150kV), CO01-CO03 (River Coln, 150kV).

**WIND**
Aggregated wind farm. Uncontrollable output — follows forecast with noise.
Zero inertia (H=0.0). No reactive capability. In GRIDCOM: WNCN (Cairn, 500MW,
220kV), WNBR (Brackley, 300MW, 150kV).

**SOLAR**
Aggregated solar farm. Uncontrollable. Zero inertia. Zero output at night.
In GRIDCOM: SLST (Stanton, 600MW, 220kV), SLFD (Feldon, 400MW, 150kV).

---

## The DC Load Flow (GRIDCOM Specific)

**What it is in GRIDCOM:**
A linear approximation that computes MW line flows and bus voltage angles.
It does NOT compute voltage magnitudes — that is the voltage model's job.

**B Matrix (susceptance matrix)**
An n×n matrix where:
- B[i,i] = sum of (1/X) for all lines connected to bus i
- B[i,j] = -(1/X) for each line between bus i and bus j
- YSHUNT_REG (1e-6) added to each diagonal for numerical stability

The slack bus (MDBY) row and column are removed before solving, giving an
(n-1)×(n-1) reduced matrix.

**P Injection Vector**
A vector of net MW injection at each non-slack bus:
P[i] = generation_mw[i] - load_mw[i]
Positive = net generation. Negative = net load.
In per-unit: divide by S_BASE.

**Solving**
θ = B_reduced⁻¹ × P_reduced
Implemented as numpy.linalg.solve(B_reduced, P_reduced).
Returns bus voltage angles in radians.

**Line Flows**
P_line(i→j) = (θᵢ - θⱼ) / Xᵢⱼ
In MW: multiply result by S_BASE.
Positive: power flows from bus i to bus j (conventional direction).
Negative: power flows from bus j to bus i (reverse).

**Line Loading**
loading_pct = |P_line_mw| / rating_mw × 100
Above 100%: overloaded. Below 100%: within rating.

---

## The Voltage Model (GRIDCOM Specific)

**What it is in GRIDCOM:**
A linear approximation that computes voltage magnitudes at each bus.
Separate from the DC load flow — solved independently.
Based on the decoupled reactive power / voltage relationship.

**B' Matrix**
Similar structure to B but built from line susceptances and shunt elements.
Used to solve: ΔV = B'⁻¹ × Q

**Q Injection Vector**
Net reactive power injection at each bus in per-unit.
Q_gen: reactive output from generators (positive = injection, negative = absorption)
Q_load: reactive demand at load buses (negative — consuming reactive)

**Voltage Solution**
ΔV = voltage deviation from nominal at each bus.
Actual voltage = 1.0 + ΔV (in per-unit).
Displayed as actual voltage (e.g. 1.024 pu or 99.2% nominal).

**VSI (Voltage Stability Index)**
VSI = V_bus / V_nominal
In GRIDCOM: V_nominal = 1.0 pu (by definition of per-unit system).
Therefore VSI = V_bus (in pu) — `bus_vsi` carries the collapse-adjusted
effective voltage (`v_eff`), identical to `bus_voltages`. `constants.py` is
authoritative for the thresholds below; `bus_vsi_tier` names the tier directly
so display never recomputes it.
Tiers (`bus_vsi_tier`):
- HEALTHY: VSI >= 0.90
- WATCH: 0.85-0.90
- WARNING: 0.70-0.85 — collapse acceleration applies below 0.85
- CRITICAL: < 0.70 (V_CRITICAL_LOW — blackout threshold)

**Voltage Collapse Acceleration**
A deliberate nonlinear fudge applied below V_WARNING_LOW (0.85) to make
collapse feel realistic (slow degradation then rapid failure). Not real
physics. Implemented as a stateful post-solve overlay owned by
`GridSimulation` (the solver itself stays pure/stateless) —
`self._v_collapse_offset: {bus: offset_pu}`, persisted tick-to-tick:
severity = (0.85 - VSI) / (0.85 - 0.70)
acceleration = severity² × COLLAPSE_GAIN
offset -= acceleration × dt   (or decays toward 0 once VSI recovers above 0.85)
v_effective = max(0.0, solved_v + offset)
Reset to 0 on blackout entry. Everything downstream (alarms, crisis,
`min_voltage_seen`, the snapshot) reads `v_effective`, never the raw solve.

**Power Factor / Substation Type**
Each load substation has a `type` (INDUSTRIAL / RESIDENTIAL / MIXED)
determining its power factor (PF) and hence its reactive draw:
Q_load = P_load × tan(acos(PF)). PF_INDUSTRIAL = 0.85 (heaviest reactive
draw), PF_RESIDENTIAL = 0.97 (lightest), PF_MIXED = 0.92. This is the
forcing function that makes voltage move — with all-zero reactive load,
every bus solves to exactly 1.0 pu regardless of topology.

**AVR Setpoint**
The per-unit voltage target a generator's Automatic Voltage Regulator holds
its bus at (`GEN_VOLTAGE_SETPOINT_DEFAULT_PU = 1.02`, editable range
`[0.95, 1.05]`). One of the player's two manual voltage-management levers.
Where multiple units share a bus, the bus's PV target is the mean of their
individual setpoints.

**Q-Reserve**
A generator's remaining headroom to its reactive limit: `q_max_mvar -
current_q_mvar` (0 once the unit has hit its limit and converted PV→PQ).
Shown to the player (`unit_q_reserve_mvar`) so they can see which nearby
generators can still help support a sagging region before raising a setpoint
further has no effect.

**Shunt Bank (Automatic)**
A capacitor (+MVAr) or reactor (−MVAr) bank at a bus, switched in discrete
steps by an automatic controller — not player-controlled. Steps toward a
voltage deadband (0.97-1.03 pu) with hysteresis and a minimum dwell time
between switches, to avoid hunting. Absorbs routine daily reactive drift.

**SVC / STATCOM (Manual)**
A continuous, player-set reactive power source at a bus (`±150 MVAr`,
`set_svc_setpoint`). The player's second manual voltage-management lever,
used where no nearby generation exists to raise a setpoint on.

---

## The Frequency Model (GRIDCOM Specific)

**Swing Equation**
Δf = F_NOMINAL × ΔP / (2 × H_system × S_BASE)
Where ΔP = total generation (MW) - total load (MW)
Applied every simulation tick as: frequency += Δf × dt_seconds

**System Inertia**
H_system = Σ(Hᵢ × S_ratedᵢ) / S_online
Where S_rated is in MVA (= rated_mw for this simulation).
S_online = total MW capacity of all ONLINE units.
Only ONLINE units contribute to inertia.

---

## Cascade and Islands

**Cascade**
A sequence of line trips where each trip causes other lines to overload and
trip, leading to a chain reaction. In GRIDCOM: triggered when a line loading
exceeds 100% for TRIP_DELAY_S seconds.

**Island**
A portion of the network that becomes electrically isolated from the rest.
Detected by breadth-first search after each line trip. Each island must
independently satisfy power balance.

**Viable Island**
An island that contains at least one reference generator (ONLINE unit that can
act as local slack) and enough generation to supply its local load.

**Non-Viable Island**
An island with insufficient generation. In GRIDCOM: immediately enters blackout
state. All buses in the island become BLACKED_OUT.

**Blackout Zone**
A set of bus labels that are currently without power. Displayed as dark nodes
with no flow animation. Restoration requires a restoration sequence.

---

## Campaign Terms

**Shift**
One operational session. In GRIDCOM: a simulated time window (2-12 hours)
played in real-time with 24:1 compression. Each shift has a defined start hour,
duration, grid size, and scripted events.

**Phase 1 (Planning)**
The pre-shift planning phase (Shifts 5-10 only). Player commits units, allocates
reserves, and schedules hydro. No time limit. Produces the initial state for Phase 2.

**Phase 2 (Real-Time)**
The operational phase. Player manages the live grid. Time is compressed 24:1.
Speed controls available. Crisis conditions force speed reduction.

**Autopilot Schedule**
The computer-generated initial dispatch used in Shifts 1-4 (before Phase 1 is
introduced). Intentionally imperfect — too little reserve, suboptimal hydro.

**Carry-Forward**
State that persists from one shift to the next: reservoir levels and unit
commitment. Tripped lines reset healthy between shifts.

**Spinning Reserve**
Available MW headroom from ONLINE units. The buffer for frequency response.
Critical metric displayed prominently. Zero spinning reserve = imminent crisis.

---

## Display Terms

**Canvas**
The 1920×844px grid schematic area (top 78% of screen). Contains the
one-line diagram of the electrical network.

**Instrument Strip**
The 1920×236px panel area (bottom 22% of screen). Contains frequency panel,
balance panel, unit dispatch list, and alarm feed.

**One-Line Diagram**
The simplified schematic representation of the electrical network. Shows
buses as symbols, lines as connections, and generation as unit squares.
Not geographically accurate — positions chosen for visual clarity.

**Native Surface**
The 1920×1080 pygame.Surface that all rendering targets. Scaled to the
player's monitor resolution at the end of each frame.

**Flow Markers**
3×3px animated squares that travel along energised lines in the direction
of power flow. Speed proportional to line loading.

**VSI Halo**
A ring drawn around a substation symbol indicating its voltage stability
tier — no ring for HEALTHY, yellow for WATCH, red for WARNING, blinking
magenta for CRITICAL (`COL_VSI_WATCH`/`WARNING`/`CRITICAL`). Drawn for every
bus whenever its tier is WATCH or worse.

---

## What GRIDCOM Does NOT Simulate

To prevent Claude Code from adding these:

- **AC power flow**: No iterative Newton-Raphson. No voltage-angle coupling.
- **Reactive losses**: No I²R or I²X losses on lines.
- **Transformer tap changers**: Not modelled at all. On-load tap-changing voltage
  regulation is not represented; routine reactive drift is handled by automatic shunt
  banks, and the player manages regional voltage with generator AVR setpoints and the
  manual SVC.
- **Protection systems**: Line trips are simplified timer-based, not relay coordination.
- **Fault currents**: No short circuit calculations.
- **Three-phase analysis**: Single-phase equivalent only (standard for transmission).
- **Stability analysis**: No eigenvalue calculations, no small-signal stability.
- **Market clearing**: No merit order algorithm — dispatch is player-controlled.
- **Unit commitment optimisation**: No MILP, no Lagrangian relaxation.
- **CO2 tracking**: Not in the simulation (noted as a Phase 9 display element only).
