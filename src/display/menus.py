"""
src/display/menus.py

Content builders for all pre-game screens: splash, main menu, mode selection,
difficulty selection, campaign intro, continuous stub, and campaign end.

All functions return data only — no rendering logic lives here.
Rendering is handled by Renderer.tick_menu_screen() and Renderer.tick_text_screen().
"""

from display.palette import (
    COL_TEXT_BODY,
    COL_TEXT_SCREEN_HDR,
)

# Colour aliases for readability
H = COL_TEXT_SCREEN_HDR   # bright green — headers, separators
B = COL_TEXT_BODY          # dim green — body text

# ─── GRIDCOM Unicode block art (COALCOM style) ───────────────────────────────
# Letters: G  R  I  D  C  O  M — 6 rows tall, box-drawing characters only.
# C, O, M reused from COALCOM; G, R, I, D designed to match.

_GRIDCOM_ART = [
    ' ██████╗  ██████╗   ██╗ ██████╗   ██████╗   ██████╗  ███    ███╗',
    '██╔════╝  ██╔══██╗  ██║ ██╔══██╗ ██╔════╝  ██╔═══██╗ ████  ████║',
    '██║  ███╗ ███████║  ██║ ██║  ██║ ██║       ██║   ██║ ██║████║██║',
    '██║   ██║ ██╔══██╝  ██║ ██║  ██║ ██║       ██║   ██║ ██║╚██╔╝██║',
    ' ██████╔╝ ██║  ╚██╗ ██║ ██████╔╝ ╚██████╗  ╚██████╔╝ ██║ ╚═╝ ██║',
    ' ╚═════╝  ╚═╝   ╚═╝ ╚═╝ ╚═════╝   ╚═════╝   ╚═════╝  ╚═╝     ╚═╝',
]

_SEP     = '═' * 64   # standard separator for text screens
_ART_SEP = '═' * 62   # separator sized to match the block-letter art width


# ─── Splash screen ────────────────────────────────────────────────────────────

def build_splash_lines() -> list:
    """Lines for the title splash screen. Rendered via tick_splash_screen()."""
    lines: list = [('', B), (_ART_SEP, H)]
    for row in _GRIDCOM_ART:
        lines.append((row, H))
    lines += [
        ('', B),
        ('GRID CONTROL TERMINAL', B),
        (_ART_SEP, H),
        ('', B),
        ('NATIONAL ENERGY CONTROL CENTRE  —  ASHFORD  —  1994', B),
        ('', B),
        ('GRIDCOM v2.4.1  /  VPC SCADA SUITE', B),
        ('', B),
    ]
    return lines


def build_menu_title_art() -> list:
    """Title block for menu screens: separator + art + subtitle + separator."""
    lines: list = [(_ART_SEP, H)]
    for row in _GRIDCOM_ART:
        lines.append((row, H))
    lines += [
        ('', B),
        ('GRID CONTROL TERMINAL', B),
        (_ART_SEP, H),
    ]
    return lines


# ─── Menu item lists ──────────────────────────────────────────────────────────

def build_main_menu_items() -> list:
    """Returns list of (label, enabled) for the main menu."""
    return [
        ('NEW GAME', True),
        ('CONTINUE',  False),   # disabled — no save system yet
        ('QUIT',      True),
    ]


def build_mode_select_items() -> list:
    """Returns list of (label, enabled) for game mode selection."""
    return [
        ('CAMPAIGN',   True),
        ('CONTINUOUS', True),
    ]


def build_difficulty_items() -> list:
    """Returns list of (label, description) for difficulty selection."""
    return [
        ('TRAINEE',    'Generous reserves. Guided events.'),
        ('OPERATOR',   'Standard reserves. Normal events.'),
        ('DISPATCHER', 'Thin reserves. Full event suite.'),
    ]


# ─── Continuous mode placeholder ──────────────────────────────────────────────

def build_continuous_placeholder_lines() -> list:
    """Placeholder screen for CONTINUOUS mode (not yet implemented)."""
    return [
        (_SEP, H),
        (' NATIONAL ENERGY CONTROL CENTRE — ASHFORD', H),
        (' CONTINUOUS MODE', H),
        (_SEP, H),
        ('', B),
        (' This mode is not yet available.', B),
        ('', B),
        (' Return to the menu and select CAMPAIGN to begin.', B),
        ('', B),
    ]


# ─── Campaign intro screens ───────────────────────────────────────────────────

def build_campaign_intro_screens() -> list:
    """
    Returns a list of 6 screen-line-lists for the campaign intro sequence.
    Each entry is passed directly to Renderer.tick_text_screen().
    Content sourced from GRIDCOM_INTRO_STORY.md.
    """
    screens = []

    # ── Screen 0 — Terminal boot ───────────────────────────────────────────────
    screens.append([
        ('', B),
        ('', B),
        (' NATIONAL ENERGY CONTROL CENTRE', H),
        (' ASHFORD', H),
        ('', B),
        (' GRIDCOM v2.4.1', H),
        (' GRID CONTROL TERMINAL', H),
        ('', B),
        (' SYSTEM INITIALISING...', B),
        ('', B),
        ('', B),
        (' 23:47  TUESDAY  08 NOVEMBER 1994', B),
    ])

    # ── Screen 1 — The Building ────────────────────────────────────────────────
    screens.append([
        ('', B),
        ('', B),
        (' The National Energy Control Centre occupies the fourth floor', B),
        (' of a building that was modern when it was built, in 1981,', B),
        (' and hasn\'t been anything since.', B),
        ('', B),
        (' The corridors smell of carpet tile and old coffee.', B),
        (' The windows face north, toward the river.', B),
        (' On a clear day you can see the hills.', B),
        ('', B),
        (' Tonight the hills are invisible.', B),
        (' It has been raining since Tuesday morning.', B),
        ('', B),
        ('', B),
        (' You have worked in this building for four months.', B),
        ('', B),
        (' Before that, you worked at Riverside for twelve years.', B),
        ('', B),
        ('', B),
        (' Riverside is different at night.', B),
        (' You know every sound it makes.', B),
        (' The boiler room has a particular resonance at low load —', B),
        (' a low harmonic that you learned to read', B),
        (' before you learned to read the instruments.', B),
        ('', B),
        (' You don\'t know what this building sounds like yet.', B),
    ])

    # ── Screen 2 — The Handover ────────────────────────────────────────────────
    screens.append([
        ('', B),
        (' The outgoing dispatcher is a man named Ferris.', B),
        (' He has been here eleven years.', B),
        (' He has the handover notes ready when you arrive.', B),
        ('', B),
        (' He goes through them quickly.', B),
        (' He has a daughter\'s school play at 08:00 and a long drive.', B),
        ('', B),
        (_SEP, H),
        (' NECC SHIFT HANDOVER  —  23:45  08/11/1994', H),
        (' OUTGOING:  R. FERRIS   (Dispatcher Grade 2)', H),
        (_SEP, H),
        ('', B),
        (' SYSTEM STATUS:    NORMAL', B),
        (' FREQUENCY:        50.01 Hz  (stable)', B),
        (' TOTAL GENERATION: 4,842 MW', B),
        (' TOTAL LOAD:       4,809 MW', B),
        (' SPINNING RESERVE:   620 MW  (adequate)', B),
        ('', B),
        (' ACTIVE ALARMS:    NONE', B),
        ('', B),
        (' UNITS OUT OF SERVICE:', B),
        ('   RVSD-2  (Riverside Coal #2) — planned outage, protection', B),
        ('            relay maintenance. Return to service 06:00.', B),
        ('', B),
        (' INTERCONNECTORS:', B),
        ('   INTC-N:  +180 MW import  (scheduled, stable)', B),
        ('   INTC-S:  on standby', B),
        ('', B),
        (' WEATHER:', B),
        ('   Rain across all regions. Wind moderate in the north.', B),
        ('   No significant renewable variation expected overnight.', B),
        ('', B),
        (' NOTES:', B),
        ('   Quiet night expected. Watch Centrefield–Midbury line', B),
        ('   loading if north wind picks up — had it at 71% earlier.', B),
        ('   Nothing else to flag.', B),
        ('', B),
        ('   Good luck.', B),
        (_SEP, H),
        ('', B),
        (' Ferris puts on his coat.', B),
        ('', B),
        (' He pauses at the door.', B),
        ('', B),
        (' He looks at the main display —', B),
        (' the grid schematic filling the screen,', B),
        (' thirty-two nodes, the backbone lines in cyan,', B),
        (' the load substations in amber,', B),
        (' the whole system breathing quietly', B),
        (' at ten minutes to midnight.', B),
        ('', B),
        (' "Frequency nominal," he says.', H),
        ('', B),
        (' He buttons his coat.', B),
        ('', B),
        (' "For now."', H),
        ('', B),
        (' The door closes.', B),
        (' The ventilation hums.', B),
        (' The cursor blinks.', B),
    ])

    # ── Screen 3 — Alone ──────────────────────────────────────────────────────
    screens.append([
        ('', B),
        (' You sit down.', B),
        ('', B),
        (' The chair is adjusted for someone taller.', B),
        (' You don\'t adjust it.', B),
        ('', B),
        (' On the desk to your left:', B),
        ('   A telephone. Internal and external lines.', B),
        ('   A logbook, today\'s page half-filled', B),
        ('   in Ferris\'s handwriting.', B),
        ('   A laminated card: EMERGENCY CONTACTS —', B),
        ('   GENERATION, TRANSMISSION, INTERCONNECTORS.', B),
        ('   A cold cup of coffee that isn\'t yours.', B),
        ('', B),
        (' On the screen in front of you:', B),
        ('   The grid.', B),
        ('', B),
        (' Thirty-two nodes.', B),
        (' Twelve hundred kilometres of transmission line.', B),
        (' Four million customers who do not know you exist.', B),
        ('', B),
        (' At Riverside you knew every unit by sound.', B),
        (' You knew which bearing on RVSD-3 ran warm in winter.', B),
        (' You knew the names of the maintenance crew', B),
        (' who came in at six to do the morning checks.', B),
        ('', B),
        (' Here you know the topology.', B),
        (' You know the load flow equations.', B),
        (' You have passed the certification.', B),
        ('', B),
        (' You know, in the way you know things', B),
        (' before you have felt them —', B),
        ('', B),
        (' that this is different.', B),
        ('', B),
        ('', B),
        (' The frequency reads 50.01 Hz.', B),
        ('', B),
        (' The grid is balanced.', B),
        ('', B),
        (' For now, that is enough.', B),
    ])

    # ── Screen 4 — The First Entry ────────────────────────────────────────────
    screens.append([
        ('', B),
        (_SEP, H),
        (' NECC OPERATIONAL LOG', H),
        (' 08/11/1994 — 09/11/1994', H),
        (_SEP, H),
        ('', B),
        (' 23:52  Shift commenced. System status normal.', B),
        ('        Handover received from R. Ferris.', B),
        ('        All parameters within normal limits.', B),
        ('        No active alarms.', B),
        ('', B),
        (' 23:52  Logged on to GRIDCOM terminal.', B),
        ('', B),
        ('', B),
        (' 23:53  Commenced watch.', H),
    ])

    # ── Screen 5 — Terminal Boot Sequence ─────────────────────────────────────
    screens.append([
        ('', B),
        (' GRIDCOM v2.4.1  —  NATIONAL ENERGY CONTROL CENTRE', H),
        (_SEP, H),
        ('', B),
        (' LOADING NETWORK TOPOLOGY...          32 nodes  OK', B),
        (' LOADING GENERATION FLEET...          47 units  OK', B),
        (' LOADING DEMAND FORECAST...                     OK', B),
        (' INITIALISING LOAD FLOW SOLVER...               OK', B),
        (' INITIALISING FREQUENCY MODEL...                OK', B),
        (' CONNECTING TO SCADA DATALINK...                OK', B),
        (' CONNECTING TO INTC-N...                        OK', B),
        (' CONNECTING TO INTC-S...                        OK', B),
        ('', B),
        (' SYSTEM HEALTH CHECK...', B),
        ('   DC LOAD FLOW:          NOMINAL', B),
        ('   VOLTAGE SOLVER:        NOMINAL', B),
        ('   FREQUENCY MONITOR:     NOMINAL', B),
        ('   ALARM SYSTEM:          NOMINAL', B),
        ('   RECORDING SYSTEM:      NOMINAL', B),
        ('', B),
        (' ALL SYSTEMS NOMINAL.', H),
        ('', B),
        (_SEP, H),
        (' GRIDCOM READY.', H),
        ('', B),
        (' CURRENT TIME:  23:53  08/11/1994', B),
        (' SYSTEM STATE:  NORMAL OPERATION', B),
        (' ACTIVE ALARMS: NONE', B),
        ('', B),
        (' SHIFT 1 OF 10  —  OVERNIGHT TROUGH', H),
        (' SIMULATED WINDOW:  02:00 — 04:00', B),
        ('', B),
        (_SEP, H),
    ])

    return screens


# ─── Campaign end screen ──────────────────────────────────────────────────────

def build_campaign_end_lines(shifts_completed: int, watch_time_s: float, grade: str) -> list:
    """
    Final screen shown after Shift 10 debrief.
    watch_time_s is total real seconds played across the campaign.
    grade is a letter grade string: 'S', 'A', 'B', 'C', or 'D'.
    """
    h = int(watch_time_s // 3600)
    m = int((watch_time_s % 3600) // 60)
    watch_str = f'{h}h {m:02d}m'

    return [
        ('', B),
        (_SEP, H),
        (' NECC OPERATIONAL LOG', H),
        (' 13/11/1994', H),
        (_SEP, H),
        ('', B),
        (' 06:00  Shift completed.', B),
        ('        Handover to incoming dispatcher.', B),
        ('        All parameters within normal limits at handover.', B),
        ('', B),
        (' 06:00  Watch concluded.', H),
        ('', B),
        ('', B),
        ('        Dispatcher Grade 2', B),
        ('        National Energy Control Centre', B),
        ('        Ashford', B),
        ('', B),
        (f'        Shifts completed:    {shifts_completed}', B),
        (f'        Total watch time:    {watch_str}', B),
        (f'        Campaign rating:     {grade}', H),
        (_SEP, H),
        ('', B),
        ('', B),
        ('        "Frequency nominal. For now."', H),
        ('                    — R. Ferris, NECC, 1994', B),
    ]
