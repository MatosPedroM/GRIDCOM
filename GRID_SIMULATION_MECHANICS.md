# Grid Simulation Mechanics
### Power Plant Simulator — Developer Reference

---

## 1. Design Philosophy

The simulation must **feel real without being real**. This means:

- Physical relationships that players can learn and exploit are preserved
- Numerical accuracy is sacrificed where it has no gameplay consequence
- Complexity is hidden behind automation until the game deliberately exposes it
- Failure modes behave correctly in shape and direction, even if not in exact magnitude

The guiding constraint: **every approximation made must preserve the phenomenology** — the way things feel when they go wrong.

---

## 2. The Fundamental Equation

Every power system, at every moment, obeys one equation:

```
Generation = Load + Losses
```

This is not optional. It is the governing constraint of the entire simulation. Everything else — frequency, voltage, stability — is a consequence of how well this balance is maintained and how the network distributes the result.

**In game terms:** the player is always, fundamentally, trying to keep this equation true across time, across space, and in the face of uncertainty.

---

## 3. Active Power and Frequency (MW / Hz)

### 3.1 The Swing Equation

Frequency is the system-wide signal of power balance. When generation exceeds load, frequency rises. When load exceeds generation, frequency falls.

```
Δf = f₀ × ΔP / (2H × S_base)

Where:
  f₀      = nominal frequency (50 Hz)
  ΔP      = power imbalance (MW) = Generation - Load
  H       = system inertia constant (seconds)
  S_base  = system rated power (MVA)
```

This equation updates every simulation tick to produce the running frequency value.

**Key insight for gameplay:** H is not fixed. It depends on which units are online and synchronized. More thermal units online = higher inertia = slower frequency response = more time for the player to react. A system dominated by renewables (low inertia) moves fast and punishes slow decisions.

### 3.2 Inertia by Unit Type

| Unit Type     | Inertia Constant H (seconds) |
|---------------|------------------------------|
| Nuclear       | 6.0                          |
| Coal          | 5.0                          |
| CCGT          | 4.0                          |
| Hydro         | 3.0                          |
| Open Cycle GT | 2.5                          |
| Wind (DFIG)   | 0.5 (synthetic only)         |
| Solar PV      | 0.0                          |

System H is the generation-weighted average of all synchronized units:

```
H_system = Σ(Hᵢ × Sᵢ) / S_online
```

### 3.3 Frequency Thresholds and Automatic Actions

| Frequency (Hz) | Condition        | Automatic Action                        |
|----------------|------------------|-----------------------------------------|
| 50.2 +         | Over-frequency   | Generator runback begins                |
| 50.0           | Nominal          | None                                    |
| 49.8           | Warning zone     | Alert displayed                         |
| 49.5           | Alert            | Reserve deployment triggered            |
| 49.2           | Emergency        | Automatic load shedding stage 1 (5%)    |
| 49.0           | Emergency        | Automatic load shedding stage 2 (10%)   |
| 48.5           | Critical         | Automatic load shedding stage 3 (15%)   |
| 47.5           | Blackout trigger | Under-frequency load shedding exhausted |

Load shedding amounts are tunable for gameplay balance. The thresholds reflect real ENTSO-E standards.

---

## 4. DC Load Flow (MW Network Distribution)

### 4.1 What DC Load Flow Gives You

DC load flow solves how MW power distributes across the transmission network. It is linear, non-iterative, and computationally trivial for a 20-bus game network.

It gives you:
- Voltage angle at every bus
- MW flow on every line
- Direction of power flow on every line
- Line loading percentage

It does not give you: voltage magnitudes, reactive power, or losses (these are handled separately).

### 4.2 The Network Model

The transmission network is represented as a graph:

```
Buses (nodes):     Generation injection points, load points, interconnection points
Lines (edges):     Transmission lines and transformers connecting buses
```

Each line has:
- Reactance X (pu) — the primary parameter for DC load flow
- MW capacity limit (thermal rating)
- Status (in service / out of service)

### 4.3 The B Matrix

The network susceptance matrix B is constructed from line reactances:

```
For a network with n buses:

B[i,i] = Σ (1/Xᵢⱼ)  for all lines connected to bus i  [diagonal]
B[i,j] = -(1/Xᵢⱼ)   for each line between bus i and j  [off-diagonal]
```

One bus is designated the **slack bus** — it absorbs the system imbalance and provides the angle reference (θ = 0). The slack bus row and column are removed before solving.

### 4.4 Solving for Angles and Flows

```
Step 1: Build the reduced B matrix (remove slack bus row/column)
Step 2: Build the net injection vector P = P_gen - P_load at each bus
Step 3: Solve: θ = B⁻¹ × P   (matrix solve, numpy.linalg.solve)
Step 4: Compute line flows: P_line(i→j) = (θᵢ - θⱼ) / Xᵢⱼ
Step 5: Compute line loading: Loading(%) = |P_line| / P_limit × 100
```

For a 20-bus network this is a 19×19 matrix solve — microseconds per tick.

### 4.5 Sign Convention

```
P_line > 0:  power flows from bus i to bus j (conventional direction)
P_line < 0:  power flows from bus j to bus i (reverse direction)
```

Both directions are physically valid. The display must show direction clearly.

### 4.6 Line Overload and Tripping

Lines are monitored every tick:

```python
if line_loading > 100%:
    overload_timer[line] += dt
    
if overload_timer[line] > trip_delay:
    trip_line(line)        # remove from topology
    rebuild_B_matrix()     # recompute network
    resolve_loadflow()     # redistribute flows
```

`trip_delay` is a tunable parameter (suggest 30-120 simulated seconds depending on severity). Instant tripping at exactly 100% feels arbitrary; delayed tripping at sustained overload feels realistic and gives the player a reaction window.

---

## 5. Voltage and Reactive Power (kV / MVAr)

### 5.1 Architectural Decision

**Voltage physics runs in the simulation from day one.** What changes between game levels is how much of it is exposed to the player and how much is managed by autopilot. This avoids an architectural rewrite when voltage mechanics are introduced.

### 5.2 The Decoupled Voltage Approximation

Reactive power and voltage magnitude are linked by a relationship analogous to the DC load flow for active power. Using the decoupled approximation:

```
ΔV = B'⁻¹ × Q

Where:
  ΔV  = voltage deviation from nominal at each bus (pu)
  Q   = net reactive injection at each bus (MVAr)
  B'  = susceptance matrix built from line charging and shunt elements
```

This is solved the same way as the DC load flow — one matrix solve, no iteration. `B'`'s diagonal carries a small numerical-stability regulariser (`VSHUNT_REG` in constants.py) to keep the matrix invertible on weak/radial buses — this also sets the overall sensitivity of voltage to Q, so it's tuned deliberately (not left at whatever value avoids a singular matrix) to keep manual Q/SVC/shunt-bank adjustments visibly effective.

**What this captures correctly:**
- Voltage sags where reactive demand is high
- Voltage supported where reactive injection exists
- Electrically weak buses sag more than strong buses
- Reactive compensation is local (cannot be transported long distances)

**What it misses:**
- Nonlinear coupling between P and Q (second-order effect, small for normal operating range)
- Exact voltage magnitude near collapse

### 5.3 Bus Types

Three bus types define how each node participates in the voltage solution:

| Bus Type | Voltage    | Reactive Injection | Description                          |
|----------|------------|--------------------|--------------------------------------|
| Slack    | Fixed (1.0 pu) | Free           | Reference bus, balances system       |
| PV       | Controlled | Bounded (Q limits) | Generator with AVR (voltage control) |
| PQ       | Free       | Fixed              | Load bus, no voltage control         |

PV buses (generators with Automatic Voltage Regulators) hold their terminal voltage at a per-unit-editable setpoint (`GEN_VOLTAGE_SETPOINT_DEFAULT_PU = 1.02`, range `[0.95, 1.05]`) by injecting or absorbing reactive power — this is Manual Lever #1 (see §5.7). Where multiple units share a bus, the bus target is the mean of their individual setpoints (physically sound: paralleled AVRs share a bus voltage).

### 5.3b Reactive Load — Per-Substation-Type Power Factor

Load buses draw reactive power as well as active power. Each load substation carries a `type` (`INDUSTRIAL` / `RESIDENTIAL` / `MIXED`), which determines its power factor and hence its reactive draw:

```
Q_load = P_load * tan(acos(PF))

PF_INDUSTRIAL  = 0.85   # heavy inductive motor load — sags voltage most
PF_RESIDENTIAL = 0.97   # mostly resistive/electronic load
PF_MIXED       = 0.92   # blended commercial/residential
```

Industrial buses draw noticeably more MVAr per MW than residential ones, so under comparable load they sag further — this is the primary forcing function that makes voltage move at all. Substation types are runtime-seeded (not yet authored into the Grid Designer JSON schema); some types also carry an automatic shunt bank (see §5.7).

### 5.4 Reactive Limits and PV→PQ Conversion

When a generator hits its reactive capability limits, it loses voltage control and becomes a PQ bus. This is one of the most important phenomena in real voltage stability:

```python
for each generator bus (PV type):
    Q_required = computed reactive injection to hold V_setpoint
    
    if Q_required > Q_max:
        # Generator at maximum reactive output — cannot hold voltage
        Q_injected = Q_max
        convert_to_PQ(bus)      # voltage now free to move
        
    elif Q_required < Q_min:
        # Generator at minimum reactive absorption
        Q_injected = Q_min  
        convert_to_PQ(bus)
        
    else:
        Q_injected = Q_required  # holding voltage successfully
```

After conversion, re-solve the voltage equations with the updated bus types. Maximum two passes — no convergence loop.

**Gameplay significance:** a generator hitting Q_max is a warning that voltage control is degrading. Multiple generators hitting limits in the same area is a precursor to voltage collapse. This is drama the player can learn to recognize.

### 5.5 Voltage Stability Index (VSI)

A per-bus voltage stability index drives both the display and the collapse mechanic. `constants.py` is authoritative for these thresholds:

```
VSI = V_bus / V_nominal   (bus_vsi in SimulationState — identical to bus_voltages,
                            both carry the collapse-adjusted effective voltage, §5.6)

VSI tiers (bus_vsi_tier):
  >= 0.90        HEALTHY   — normal operation (V_WATCH_LOW)
  0.85 - 0.90    WATCH     — monitoring warranted (V_WARNING_LOW)
  0.70 - 0.85    WARNING   — collapse acceleration begins (V_CRITICAL_LOW)
  < 0.70         CRITICAL  — cascade imminent
```

### 5.6 Voltage Collapse Acceleration

The linear decoupled model underestimates how rapidly voltage deteriorates near collapse. A nonlinear correction is applied in the collapse zone only. Because the solver itself is a stateless, pure matrix solve, this correction is implemented as a **stateful post-solve overlay owned by the simulation**, not inside the solver:

```python
V_COLLAPSE_SEVERITY_LOW   = 0.85   # == V_WARNING_LOW — severity 0 here
V_COLLAPSE_SEVERITY_FLOOR = 0.70   # == V_CRITICAL_LOW — severity 1 here
V_COLLAPSE_GAIN = 2.0
V_COLLAPSE_RECOVERY_PU_S = 0.02    # offset decay rate when voltage recovers

# Once per tick, after the solve, per bus:
if solved_v < V_WARNING_LOW:
    severity = clamp((V_COLLAPSE_SEVERITY_LOW - solved_v) /
                      (V_COLLAPSE_SEVERITY_LOW - V_COLLAPSE_SEVERITY_FLOOR), 0, 1)
    accel = severity ** 2 * V_COLLAPSE_GAIN
    offset -= accel * dt
else:
    offset = min(0.0, offset + V_COLLAPSE_RECOVERY_PU_S * dt)   # decays back to 0

v_effective = max(0.0, solved_v + offset)
```

`v_effective` (never the raw solve) is what alarms, crisis detection, `min_voltage_seen`, and the display all see. The offset persists tick-to-tick in `GridSimulation._v_collapse_offset` — this produces the correct phenomenology (slow degradation in the warning zone, then rapidly accelerating collapse below the critical point) and lets a mismanaged bus keep worsening even though the underlying solve is instantaneous and stateless. The offset resets to 0 for any bus that enters a blackout zone, and decays back toward 0 once the operator relieves the underlying reactive deficiency (raises a generator setpoint, switches in a shunt, or the auto-regulators catch up) — it does not require player action to "clear," only for the voltage to genuinely recover.

### 5.7 Reactive Compensation Assets — Automatic Regulators and Manual Levers

Reactive compensation is **local** — it cannot be transported across the network the way MW can. A sagging region can only be supported by generation or a device *in that region*. This is the central gameplay implication of voltage physics: the grid must be managed regionally, not just kept fully connected.

All devices are modelled as Q injections at a bus (never as B' edits — switching a device never re-factorises the voltage matrix):

| Asset Type          | MVAr          | Control                          | Player interaction        |
|----------------------|---------------|-----------------------------------|----------------------------|
| Shunt capacitor/reactor bank | ±discrete steps | Deadband + hysteresis auto-switching | **Read-only** — automatic |
| Generator Q target   | Continuous, bounded by `q_max_mvar`/`q_min_mvar` | Direct MVAr setpoint (`Q` key + Up/Down) | **Manual — Lever #1** |
| SVC / STATCOM        | ±150 MVAr continuous | Direct setpoint | **Manual — Lever #2** |

**The automatic shunt bank** absorbs the grid's routine daily reactive drift so the player isn't fighting minor fluctuations continuously. It uses a hunting-resistant control pattern:
- A **deadband** (switch in below 0.97 pu, switch out above 1.03 pu) so it doesn't react to noise around the setpoint.
- **Hysteresis** implicit in the deadband width itself.
- A **minimum dwell time** between switches (`SHUNT_SWITCH_DWELL_S`) so a bank that has just moved doesn't immediately reverse.
- A **one-tick lag**: automatics act on the *previous* tick's solved voltage, evaluated once per tick before that tick's Q injections are built — never inside the solve itself. This means there is no algebraic loop with the solver, and at the simulation's 10 Hz tick rate the lag is imperceptible to the player.

**The two manual levers** are the tools the player actively works:
1. **Generator Q target** (`set_unit_q_target`, bound to the `Q` key + Up/Down in-game) — supports a sagging region from nearby generation. Every bus is solved PQ; there is no AVR or voltage setpoint to hold — the player sets the unit's reactive injection directly in MVAr, clamped to `[q_min_mvar, q_max_mvar]`, and the solver's `ΔV = B'⁻¹ × Q` reflects it immediately. This replaced the original PV-bus/AVR-setpoint model (voltage target with automatic Q correction) — see STAGE_STATUS.md's F9 session for the rework.
2. **Manual SVC/STATCOM** — a continuous, player-set MVAr source at a specific bus, for regions with no nearby generation to lean on.

Both levers move real, but locally small, voltage — see §5.2's `VSHUNT_REG` note on solver sensitivity.

---

## 6. Ramp Rates and Unit Commitment

### 6.1 Ramp Rates

No unit can change output instantaneously. Ramp rates constrain how quickly dispatch decisions take effect. Ramp rate is an absolute MW/min value looked up by unit_type from constants.py's UNIT_DEFAULTS — not a percentage of that unit's own rated_mw, and not authored per-unit in grid JSON, so retuning a technology's ramp rate never requires editing grid files:

| Unit Type     | Ramp Rate (MW/min) | Cold Start Time |
|---------------|---------------------|-----------------|
| Nuclear       | 3.5                 | 8 hours         |
| Coal          | 4.0                 | 4 hours         |
| CCGT          | 15.0                | 1 hour          |
| Hydro         | 250                 | 5-8 minutes     |
| Wind / Solar  | Uncontrollable      | N/A             |

**Implementation:**

```python
def update_unit_output(unit, target_MW, dt_minutes):
    max_change = unit.ramp_mw_per_min * dt_minutes
    actual_change = clamp(target_MW - unit.current_MW, 
                          -max_change, 
                          +max_change)
    unit.current_MW += actual_change
```

### 6.2 Unit States

Units exist in one of four states:

```
OFFLINE      → not synchronized, not available
STARTING     → start sequence in progress (duration = cold_start_time)
SYNCHRONIZED → online, contributing inertia, can dispatch
SHUTDOWN     → shutdown sequence in progress (duration = ~10 minutes)
```

Only SYNCHRONIZED units contribute to:
- Available generation
- System inertia (H calculation)
- Reactive capability (voltage control)

### 6.3 Minimum Up/Down Times

Real units cannot be cycled arbitrarily:

```
min_up_time:   minimum hours a unit must stay online once started
min_down_time: minimum hours a unit must stay offline before restarting
```

These create the strategic commitment problem: starting a unit is a multi-hour decision, not a real-time one. This is where day-ahead planning mechanics become relevant in later game levels.

---

## 7. Demand Model

### 7.1 Demand Composition

```
Demand(t) = Base_profile(hour, day_type) 
           × Temperature_factor(T) 
           + Stochastic_noise(σ)
           + Industrial_block(if any)
```

### 7.2 Daily Profile

A normalized daily profile (pu of peak) representing a typical weekday:

```
Hour:  0    1    2    3    4    5    6    7    8    9   10   11
Load: 0.65 0.61 0.58 0.57 0.57 0.60 0.66 0.74 0.82 0.87 0.89 0.90

Hour: 12   13   14   15   16   17   18   19   20   21   22   23
Load: 0.89 0.86 0.85 0.85 0.87 0.91 0.95 0.98 1.00 0.97 0.90 0.78
```

Weekend profile is approximately 85% of weekday profile with a flatter shape.

### 7.3 Temperature Sensitivity

```python
def temperature_factor(T_celsius):
    T_ref = 18.0   # comfort temperature (no heating/cooling load)
    if T_celsius < T_ref:
        return 1.0 + 0.015 * (T_ref - T_celsius)  # heating load
    else:
        return 1.0 + 0.010 * (T_celsius - T_ref)  # cooling load
```

### 7.4 Forecast vs. Actual

The player operates against a **forecast**. Actual demand deviates from forecast by a stochastic term:

```python
noise_sigma = 0.02 * peak_demand   # 2% standard deviation
actual_demand = forecast_demand + random.gauss(0, noise_sigma)
```

This deviation — the forecast error — creates the moment-to-moment real-time balancing challenge. The player can see the forecast; they cannot see the actual until the tick runs.

---

## 8. Renewable Generation

### 8.1 Wind

Wind output follows a power curve relationship to wind speed:

```
P_wind = 0                           if V < V_cutin  (typically 3 m/s)
P_wind = P_rated × (V³/V_rated³)    if V_cutin < V < V_rated
P_wind = P_rated                     if V_rated < V < V_cutout  (typically 25 m/s)
P_wind = 0                           if V > V_cutout
```

Wind speed is a stochastic process with persistence (tomorrow's wind is correlated with today's). The player sees a wind forecast; actual varies around it.

### 8.2 Solar

Solar output follows an irradiance profile modulated by cloud cover:

```python
def solar_output(hour, cloud_factor, panel_MW):
    irradiance = max(0, sin(π × (hour - 6) / 12))   # sunrise 6, sunset 18
    return panel_MW × irradiance × (1 - 0.75 × cloud_factor)
```

Cloud cover is a stochastic variable with slower time-scale variation than minute-to-minute noise.

### 8.3 Key Constraint

Renewables contribute **zero inertia** (or very low synthetic inertia). High renewable penetration means lower system H, faster frequency dynamics, and less time for the player to react to disturbances. This is a core game mechanic in later levels.

---

## 9. Cascade Failure Model

### 9.1 Cascade Sequence

```
1. TRIGGER
   Line overloads beyond threshold for trip_delay seconds
   → Line trips (removed from topology)

2. REDISTRIBUTION
   B matrix rebuilt without tripped line
   Load flow re-solved
   Power redistributes to remaining lines (kirchhoff)

3. CHECK
   Other lines may now be overloaded
   If yes → repeat from step 1 (cascade continues)
   If no  → cascade arrested, system stabilizes in degraded state

4. FREQUENCY IMPACT
   Each tripped line may isolate generation → frequency drops
   Each tripped line may isolate load → frequency rises
   Swing equation updates with new generation/load balance

5. ISLAND DETECTION
   Check network connectivity
   If network splits → each island runs independent frequency
   Islands with generation deficit → blackout that island
```

### 9.2 Island Detection

```python
def find_islands(buses, lines_in_service):
    # Breadth-first search from each unvisited bus
    visited = set()
    islands = []
    for bus in buses:
        if bus not in visited:
            island = bfs(bus, lines_in_service)
            islands.append(island)
            visited.update(island)
    return islands
```

Each island must independently satisfy power balance. Islands without a slack bus (reference generator) collapse.

### 9.3 Blackout Zones

When an island cannot maintain frequency (generation < load and no more load shedding available), it enters blackout state. Restoration requires:

1. Isolate the affected area (open boundary lines)
2. Black-start capable unit within the island (or energize from adjacent island)
3. Sequential load restoration at controlled rate

This can be a gameplay mechanic in itself.

---

## 10. The Simulation Loop

Every game tick executes in this order:

```python
def simulation_tick(dt):

    # 1. Update exogenous inputs
    demand = update_demand(hour, temperature, noise)
    wind_actual = update_wind(wind_speed_actual)
    solar_actual = update_solar(hour, cloud_cover)

    # 2. Update unit states (start sequences, ramp rates)
    for unit in units:
        unit.update_state(dt)
        unit.ramp_toward_dispatch_target(dt)

    # 3. Compute power imbalance
    total_generation = sum(unit.current_MW for unit in synchronized_units)
    total_load = demand + losses_estimate()
    imbalance = total_generation - total_load

    # 4. Update frequency (swing equation)
    H_system = compute_system_inertia()
    df = f_nominal * imbalance / (2 * H_system * S_base)
    frequency += df * dt
    apply_agc_response(frequency_deviation)
    check_frequency_thresholds()

    # 5. Solve DC load flow (MW flows and angles)
    P_injections = build_injection_vector()
    theta = solve_dc_loadflow(B_matrix, P_injections)
    mw_flows = compute_line_flows(theta)
    line_loading = compute_loading(mw_flows)

    # 6. Solve voltage (decoupled approximation)
    Q_injections = build_reactive_injection_vector()
    voltages = solve_voltage(B_prime, Q_injections)
    check_reactive_limits()        # PV → PQ conversion, max 2 passes
    apply_collapse_acceleration()  # nonlinear correction below 0.85 pu

    # 7. Check line overloads and trip if sustained
    for line in lines:
        update_overload_timer(line, line_loading[line], dt)
        if overload_timer[line] > trip_delay:
            trip_line(line)

    # 8. Cascade check
    if any_line_tripped_this_tick:
        rebuild_network()
        solve_dc_loadflow()        # re-check after topology change
        check_islands()

    # 9. Update display state
    publish_state_to_display()
```

---

## 11. Game Level Progression (Simulation Exposure)

| Level | Player Controls                    | Autopilot Manages              | Key New Mechanic              |
|-------|------------------------------------|--------------------------------|-------------------------------|
| 1     | Unit dispatch (MW setpoints)       | Voltage, reactive, commitment  | Frequency, spinning reserve   |
| 2     | + Unit commitment decisions        | Voltage, reactive              | Start times, min up/down      |
| 3     | + Reactive dispatch, compensation  | Shunt banks                    | Voltage profiles, Q limits    |
| 4     | + Regional voltage support, islanding | Nothing                     | Cascade management, restoration|
| 5     | + Market bidding, forecast risk    | Nothing                        | Day-ahead commitment under uncertainty |

The simulation engine does not change between levels. The **autopilot layer** fills in what the player is not yet managing. As levels progress, autopilot responsibility transfers to the player.

---

## 12. Numerical Implementation Notes

### Dependencies
- **numpy**: Matrix construction and solve (`numpy.linalg.solve`)
- **scipy.sparse** (optional): For larger networks — not needed for ≤ 20 buses
- No external power system libraries required

### Performance Targets
- 20-bus network load flow solve: < 1 ms per tick
- Full simulation tick (all steps): < 5 ms per tick
- Target simulation rate: 10 ticks/second (= 10 simulated minutes/second at 1:1 time ratio)

### Numerical Robustness
- **Singular B matrix**: occurs if network is split (islanded). Detect connectivity before solving.
- **Near-singular**: occurs with very high X lines (weak connections). Add small shunt admittance to each bus (Yshunt = 1e-6) to regularize.
- **Frequency runaway**: clamp frequency to [45, 55] Hz regardless of imbalance. Below 47.5 Hz, declare blackout.

### Units and Per-Unit System
- All internal calculations in per-unit (pu)
- Base MVA: 1000 MVA (or largest unit in system)
- Base voltage: nominal voltage at each bus (400 kV, 220 kV, etc.)
- Display conversions: multiply by base values for MW, MVAr, kV display

---

## 13. Parameters Reference

### Tunable Game Parameters

| Parameter           | Suggested Value | Effect of Increasing               |
|---------------------|-----------------|------------------------------------|
| noise_sigma         | 2% of peak      | More frequent real-time imbalances |
| trip_delay          | 60 seconds      | More time to prevent cascade       |
| collapse_gain       | 0.5             | Faster voltage collapse in danger zone |
| load_shed_steps     | 5%, 10%, 15%    | How much load shedding buys before blackout |
| H_thermal_avg       | 5.0 seconds     | Higher = more stable frequency     |

These parameters are the primary levers for difficulty tuning without changing the simulation structure.

---

*Document version 1.0 — covers simulation engine design for all game levels. Update as mechanics are validated through prototyping.*
