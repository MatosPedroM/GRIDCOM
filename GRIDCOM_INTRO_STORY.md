# GRIDCOM : Grid Control Terminal
### Intro Story — Narrative Reference Document

---

## 1. Narrative Overview

The intro story establishes the player character, the fictional world, and the emotional tone of the game before the first shift begins. It is told through a combination of text screens and terminal boot sequence — no voice acting, no cutscenes. Pure text on dark screens, in the visual language of the game itself.

The story is experienced once at the start of a new campaign. It cannot be skipped on a first playthrough. On subsequent playthroughs it can be skipped after the opening terminal sequence.

---

## 2. Fictional World Reference

```
COUNTRY:            Unnamed
CAPITAL:            Ashford
GRID OPERATOR:      National Energy Control Centre (NECC)
INCUMBENT UTILITY:  VPC  (Valdoria Power Corporation)
INTERCONNECTORS:    Interconnection North (INTC-N)  ±800MW
                    Interconnection South (INTC-S)  ±600MW
YEAR:               1994
PLAYER CHARACTER:   Senior Grid Dispatcher, NECC
                    Previously: Senior Control Room Operator,
                    Riverside Coal Power Station (12 years)
OUTGOING DISPATCHER: Ferris
```

---

## 3. The Intro Sequence

---

### SCREEN 1 — Darkness

*Black screen. Silence. Then, slowly, the sound of a building at night — ventilation hum, the distant click of a relay somewhere down the corridor. A single cursor blinks in the centre of the screen.*

*Five seconds pass.*

*Text appears, one line at a time, as if typed:*

```
NATIONAL ENERGY CONTROL CENTRE
ASHFORD

GRIDCOM v2.4.1
GRID CONTROL TERMINAL

SYSTEM INITIALISING...
```

*A pause. Then:*

```
23:47  TUESDAY  08 NOVEMBER 1994
```

*Another pause. Then the cursor blinks three times and the screen clears.*

---

### SCREEN 2 — The Building

```
The National Energy Control Centre occupies the fourth floor
of a building that was modern when it was built, in 1981,
and hasn't been anything since.

The corridors smell of carpet tile and old coffee.
The windows face north, toward the river.
On a clear day you can see the hills.

Tonight the hills are invisible.
It has been raining since Tuesday morning.
```

*Pause.*

```
You have worked in this building for four months.

Before that, you worked at Riverside for twelve years.
```

*Pause. Then, quieter:*

```
Riverside is different at night.
You know every sound it makes.
The boiler room has a particular resonance at low load —
a low harmonic that you learned to read
before you learned to read the instruments.

You don't know what this building sounds like yet.
```

---

### SCREEN 3 — The Handover

```
The outgoing dispatcher is a man named Ferris.
He has been here eleven years.
He has the handover notes ready when you arrive.

He goes through them quickly.
He has a daughter's school play at 08:00 and a long drive.
```

*The handover notes appear on screen, formatted as a real operational document:*

```
──────────────────────────────────────────────────────────────
NECC SHIFT HANDOVER  —  23:45  08/11/1994
OUTGOING:  R. FERRIS   (Dispatcher Grade 2)
INCOMING:  [PLAYER]    (Dispatcher Grade 2)
──────────────────────────────────────────────────────────────

SYSTEM STATUS:    NORMAL
FREQUENCY:        50.01 Hz  (stable)
TOTAL GENERATION: 4,842 MW
TOTAL LOAD:       4,809 MW
SPINNING RESERVE:   620 MW  (adequate)

ACTIVE ALARMS:    NONE

UNITS OUT OF SERVICE:
  RVSD-2  (Riverside Coal #2) — planned outage, protection
           relay maintenance. Return to service 06:00 tomorrow.

INTERCONNECTORS:
  INTC-N:  +180 MW import  (scheduled, stable)
  INTC-S:  on standby

WEATHER:
  Rain across all regions. Wind moderate in the north.
  No significant renewable variation expected overnight.

NOTES:
  Quiet night expected. Watch Centrefield–Midbury line
  loading if north wind picks up — had it at 71% earlier
  this evening. Nothing else to flag.

  Good luck.
──────────────────────────────────────────────────────────────
```

*A pause after the document. Then:*

```
Ferris puts on his coat.

He pauses at the door.

He looks at the main display —
the grid schematic filling the screen,
thirty-two nodes, the backbone lines in cyan,
the load substations in amber,
the whole system breathing quietly
at ten minutes to midnight.

"Frequency nominal," he says.

He buttons his coat.

"For now."

The door closes.
The ventilation hums.
The cursor blinks.
```

---

### SCREEN 4 — Alone

```
You sit down.

The chair is adjusted for someone taller.
You don't adjust it.

On the desk to your left:
  A telephone. Internal and external lines.
  A logbook, today's page half-filled
  in Ferris's handwriting.
  A laminated card: EMERGENCY CONTACTS —
  GENERATION, TRANSMISSION, INTERCONNECTORS.
  A cold cup of coffee that isn't yours.

On the screen in front of you:
  The grid.

Thirty-two nodes.
Twelve hundred kilometres of transmission line.
Four million customers who do not know you exist.

At Riverside you knew every unit by sound.
You knew which bearing on RVSD-3 ran warm in winter.
You knew the names of the maintenance crew
who came in at six to do the morning checks.

Here you know the topology.
You know the load flow equations.
You have passed the certification.

You know, in the way you know things
before you have felt them —

that this is different.
```

*Pause.*

```
The frequency reads 50.01 Hz.

The grid is balanced.

For now, that is enough.
```

---

### SCREEN 5 — The First Entry

*The logbook appears on screen, formatted as a real operational log:*

```
──────────────────────────────────────────────────────
NECC OPERATIONAL LOG
08/11/1994 — 09/11/1994
DISPATCHER:  [PLAYER NAME]
──────────────────────────────────────────────────────

23:52  Shift commenced. System status normal.
       Handover received from R. Ferris.
       All parameters within normal limits.
       No active alarms.

23:52  Logged on to GRIDCOM terminal.
```

*The cursor blinks after the last line.*

*A pause.*

*Then the final log entry completes itself, one character at a time:*

```
23:53  Commenced watch.
```

*The screen holds on that line for three seconds.*

*Then:*

```
                    [ PRESS ANY KEY TO BEGIN ]
```

---

### SCREEN 6 — Terminal Boot

*The screen clears. The GRIDCOM terminal boot sequence begins:*

```
GRIDCOM v2.4.1  —  NATIONAL ENERGY CONTROL CENTRE
════════════════════════════════════════════════════

LOADING NETWORK TOPOLOGY...          32 nodes  OK
LOADING GENERATION FLEET...          47 units  OK
LOADING DEMAND FORECAST...                     OK
INITIALISING LOAD FLOW SOLVER...               OK
INITIALISING FREQUENCY MODEL...                OK
CONNECTING TO SCADA DATALINK...                OK
CONNECTING TO INTC-N...                        OK
CONNECTING TO INTC-S...                        OK

SYSTEM HEALTH CHECK...
  DC LOAD FLOW:          NOMINAL
  VOLTAGE SOLVER:        NOMINAL
  FREQUENCY MONITOR:     NOMINAL
  ALARM SYSTEM:          NOMINAL
  RECORDING SYSTEM:      NOMINAL

ALL SYSTEMS NOMINAL.

════════════════════════════════════════════════════
GRIDCOM READY.

CURRENT TIME:  23:53  08/11/1994
SYSTEM STATE:  NORMAL OPERATION
ACTIVE ALARMS: NONE

SHIFT 1 OF 10  —  OVERNIGHT TROUGH
SIMULATED WINDOW:  02:00 — 04:00

DISPATCHER ON WATCH: [PLAYER NAME]
════════════════════════════════════════════════════
```

*The grid canvas loads. The schematic fills the screen — the instrument strip at the bottom, the frequency reading 50.01 Hz in green, the flow markers moving quietly along the backbone lines.*

*The game begins.*

---

## 4. The Short Story

*The following prose piece is the creative foundation from which the game's tone and motto emerged. It is retained here as a narrative reference for writers and developers working on subsequent shift intros, UI copy, and any future narrative content.*

---

The overnight shift starts at midnight.

You take the chair, adjust the headset, sign the log. The outgoing dispatcher — Ferris, eleven years on this desk — gives you the handover in four sentences. System normal. Interconnection North import steady. Watch the Centrefield–Midbury line if the north wind picks up. Good luck.

He leaves. The door closes.

The screen in front of you shows the grid. Thirty-two nodes. The backbone lines pulse cyan in the dark. Load substations glow amber. Somewhere in the north, three hydro units turn quietly on the same river they've been turning on for forty years. Somewhere in the south, Riverside's two remaining coal units breathe at half load, the boilers ticking over, keeping the pressure up for a demand that won't come until morning.

You know Riverside. You spent twelve years there. You know the sound RVSD-2 makes when it's running warm. You know the name of the man who checks the bearings at six.

Here you know something larger and less personal. You know that the number at the top of the frequency display — 50.01 — is the only number that matters. You know that if it moves, everything moves. You know that four million people are asleep right now, their refrigerators humming, their phone chargers drawing a few quiet watts, their heating cycling on and off through the small hours — and not one of them is thinking about this room, this screen, this number.

They don't need to.

That's the job. Not the emergencies — though there will be emergencies. The job is the 50.01. The job is the calm. The job is arriving at six in the morning with nothing in the log worth reading.

At 02:00 something trips in the north.

You reach for the keyboard.

---

The alarm is yellow. Centrefield–Midbury line. Loading at 91%.

Not a crisis. Not yet.

You pull up the flow display. Wind in the north came up faster than forecast — the model had it at moderate, it's running strong. Power pushing south through the line, doing work it wasn't scheduled to do at two in the morning.

You check the reserve. 580 MW spinning. Enough.

You call the Kelmore hydro complex on the direct line. Three rings.

"Kelmore."

"Dispatch. I need KELM-1 down 60 megawatts. Centrefield line is loading."

A pause. The sound of someone checking something.

"KELM-1 coming down. Give me ninety seconds."

You watch the display. The flow markers slow. The loading percentage moves — 91, 89, 86. The alarm clears at 84%.

You make the log entry.

*02:17  Centrefield–Midbury loading event. North wind above
forecast. KELM-1 redispatched −60MW. Line loading returned
to normal limits. Alarm cleared.*

Four sentences.

Four million people turn over in their sleep.

The frequency reads 50.00.

You pour the coffee that's been sitting since eleven. It's cold. You drink it anyway.

---

At 03:40 the frequency moves.

Not much. 49.87. But it moves.

You're already looking at the generation board when the second alarm comes in. Riverside. RVSD-3 — the unit you know better than any other unit on this grid — has tripped on overcurrent protection. 300 megawatts, gone in a second.

You don't panic. You've felt this before from the other side — the sudden lurch, the pressure drop, the scramble in the control room. You were the one calling dispatch twelve years ago, telling them what happened, waiting for instructions.

Now you are dispatch.

You check the inertia. 4.6 seconds. Enough time.

The droop response is already working — the other units feeling the frequency drop, opening their governors, pushing a little more. Automatic. Physics. You watch the frequency stabilise at 49.81 and hold.

You pick up the phone.

"Wrentham CCGT. I need WRNG-1 to 380 megawatts. Frequency event."

"WRNG-1 ramping. Two minutes to full output."

"Confirmed."

You watch the frequency climb back. 49.85. 49.91. 49.97. 50.01.

You exhale.

The log entry takes thirty seconds to write.

Nobody will read it.

That's fine.

---

## 5. Narrative Tone Notes

**Understatement is the mode.** The weight of the situation comes from specificity and restraint, not from dramatic language. "Four million customers who do not know you exist" is more powerful than any explicit statement of stakes.

**The Riverside reference is the emotional core.** The player character's competence is established (twelve years, senior operator) and their displacement is established simultaneously — they know RVSD-3's bearing, they don't know this building's sounds yet. That gap is the emotional starting point for the entire campaign.

**Ferris's exit lines are the game's thesis and motto delivered in character.** "Frequency nominal. For now." is not a dramatic statement. It is what a tired dispatcher says on his way out the door after eleven years. The player hears it as small talk. The campaign turns it into something larger.

**"Commenced watch" is the transition ritual.** Real grid operators write this. It is a real phrase from real operational logs. The moment the player presses any key, they have commenced watch. The game holds them to that.

**The cold coffee is load-bearing.** It appears twice — once in the desk inventory, once drunk at 02:20. It is the most human detail in the story. Keep it.

---

## 6. The Motto

```
"Frequency nominal. For now."
                    — R. Ferris, NECC, 1994
```

Delivered by Ferris at the door, on his way out, without breaking stride. Not a warning. Not wisdom. Just what you say after eleven years on this desk when you know what "nominal" actually means.

---

## 7. Subsequent Shift Intros

Shifts 2-10 do not repeat the full intro. Each shift begins with a single logbook entry appearing on screen before the terminal boot sequence:

```
NECC OPERATIONAL LOG
[DATE]
DISPATCHER:  [PLAYER NAME]

[TIME]  Shift commenced.
        Handover from [NAME].
        [One line of operational context specific to this shift.]
        Logged on to GRIDCOM terminal.

[TIME]  Commenced watch.

                    [ PRESS ANY KEY TO BEGIN ]
```

The single context line is written specifically for each shift's operational character:

```
SHIFT 1   "System quiet. Overnight trough. Watch the north wind."
SHIFT 2   "Morning ramp beginning. Solar forecast uncertain."
SHIFT 3   "Mid-morning plateau. Congestion risk on northern path."
SHIFT 4   "Evening peak. Solar collapsing at sunset. Reserves tight."
SHIFT 5   "Full grid active. Interconnection North scheduled at
           400MW import. Plan accordingly."
SHIFT 6   "Peak demand period. N-1 security marginal in the west.
           Know your restoration sequence."
SHIFT 7   "Full morning cycle. Voltage profiles tight on southern
           load buses. Reactive reserves committed."
SHIFT 8   "Solar peak then collapse. Kelmore reservoir positioning
           is everything today."
SHIFT 9   "Ten hours. Full hydro-thermal coordination.
           The cheap plan is usually the dangerous one."
SHIFT 10  "Storm system forecast from the west. Twelve hours.
           Everything you know. All at once."
```

By Shift 10 the player has read ten of these entries. The ritual is established. "Commenced watch" has accumulated meaning across the entire campaign.

---

## 8. Campaign Ending

After Shift 10's debrief screen, a final logbook entry appears:

```
──────────────────────────────────────────────────────
NECC OPERATIONAL LOG
[FINAL DATE]
DISPATCHER:  [PLAYER NAME]
──────────────────────────────────────────────────────

[TIME]  Shift completed.
        Handover to [NAME].
        [One line summary of the campaign's final state.]

[TIME]  Watch concluded.

        [PLAYER NAME]
        Dispatcher Grade 2
        National Energy Control Centre
        Ashford

        Shifts completed:       10
        Total watch time:       [REAL TIME PLAYED]
        Campaign rating:        [LETTER GRADE]
──────────────────────────────────────────────────────
```

*A pause. Then, below the entry, a single line appears:*

```
        "Frequency nominal. For now."
                            — R. Ferris, NECC, 1994
```

*The screen holds.*

*Then fades to black.*

---

## 9. Canonical Reference — Locked Decisions

The following elements are locked and should be used consistently across all GRIDCOM narrative content:

```
ELEMENT                   VALUE
────────────────────────────────────────────────────────
Country name              Unnamed
Capital city              Ashford
Grid operator             National Energy Control Centre (NECC)
Incumbent utility         VPC
Interconnectors           INTC-N (North), INTC-S (South)
Year                      1994
Outgoing dispatcher       R. Ferris  (Dispatcher Grade 2, 11 years)
Player character          Dispatcher Grade 2, ex-Riverside (12 years)
Game motto                "Frequency nominal. For now."
Motto attribution         R. Ferris, NECC, 1994
Transition ritual         "Commenced watch."
Riverside easter egg      RVSD-2 out of service in Shift 1 handover notes
Cold coffee               Appears on desk and consumed at 02:20 — keep it
────────────────────────────────────────────────────────
```

---

*Document version 2.0 — full rewrite incorporating all locked naming decisions. Replaces version 1.0. All fictional world elements in this document supersede any conflicting references in other GRIDCOM documents. Update GRID_TOPOLOGY_AND_DISPLAY.md and GAMEPLAY_REFERENCE.md with new place names and interconnector labels at next revision.*
