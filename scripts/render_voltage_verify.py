"""
scripts/render_voltage_verify.py

Phase D verification: render a frame with seeded reactive devices and a
sagging bus to an offscreen surface, save as PNG for visual inspection.
No live window — matches established project precedent (see STAGE_STATUS.md
sessions 46/49) for headless display verification.

Run: SDL_VIDEODRIVER=dummy python scripts/render_voltage_verify.py
"""

import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pygame
import pygame.freetype

pygame.init()
pygame.freetype.init()

from data.designer_io import DesignerBus, DesignerLine, DesignerUnit
from simulation.designer_grid import DesignerGrid
from simulation.simulation import GridSimulation
from simulation.reactive_devices import ShuntBank, SVC
from display.renderer import Renderer
from simulation.constants import NATIVE_WIDTH, NATIVE_HEIGHT

buses = [
    DesignerBus(label='SLK', name='Slack', voltage_kv=400.0,
                bus_type='TRANSMISSION', canvas_x=300, canvas_y=200,
                active_from_shift=1, is_slack=True),
    DesignerBus(label='GEN', name='Support gen', voltage_kv=400.0,
                bus_type='TRANSMISSION', canvas_x=600, canvas_y=200,
                active_from_shift=1, is_slack=False),
    DesignerBus(label='WEAK', name='Weak', voltage_kv=150.0,
                bus_type='LOAD', canvas_x=900, canvas_y=200,
                active_from_shift=1, is_slack=False, peak_load_mw=850.0),
]
lines = [
    DesignerLine(label='L1', from_bus='SLK', to_bus='GEN',
                 reactance_pu=0.05, rating_mw=2000.0, voltage_kv=400.0),
    DesignerLine(label='L2', from_bus='GEN', to_bus='WEAK',
                 reactance_pu=0.30, rating_mw=2000.0, voltage_kv=150.0),
]
units = [
    DesignerUnit(label='GEN-1', station_label='GEN', bus_label='GEN',
                 unit_type='CCGT', rated_mw=1000.0, min_mw=0.0,
                 inertia_h=4.0, cold_start_min=5.0,
                 q_max_mvar=200.0, q_min_mvar=-200.0, can_pump=False,
                 active_from_shift=1, description='support gen', station_x=600, station_y=150),
]
grid = DesignerGrid(buses, lines, units)

sim = GridSimulation(
    grid=grid,
    shift_number=1,
    difficulty='standard',
    initial_schedule={'GEN-1': 850.0},
    substation_load_mw={'WEAK': {h: 850.0 for h in range(25)}},
    substation_types={'WEAK': 'INDUSTRIAL'},
    start_hour=12.0,
    duration_hours=1.0,
)
sim._reactive.add_shunt_bank(ShuntBank(bus='WEAK'))
sim._reactive.add_svc(SVC(bus='WEAK'))

for _ in range(20):
    sim.tick(1.0)

state = sim.get_state()
print(f'WEAK voltage: {state.bus_voltages["WEAK"]:.4f}, tier: {state.bus_vsi_tier["WEAK"]}')
print(f'shunt step: {state.bus_shunt_step.get("WEAK")}')
print(f'crisis_active: {state.crisis_active}, crisis_type: {state.crisis_type}')

display_surf = pygame.display.set_mode((NATIVE_WIDTH, NATIVE_HEIGHT))
renderer = Renderer(display_surf, shift=1, display_size=(NATIVE_WIDTH, NATIVE_HEIGHT))
renderer.set_designer_grid(grid)

# Select WEAK bus so its context panel (VSI tier, Q, shunt row, SVC row) renders
renderer._selected_label = 'WEAK'
renderer.on_svc_adjust(sim, +1)  # exercise the manual SVC command path

renderer.tick(0.016, state=sim.get_state(), speed_mult=0)
renderer.tick(0.016, state=sim.get_state(), speed_mult=0)  # second frame, blink_on settled

out_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'scratchpad_render')
out_dir = r'C:\Users\Pedro\AppData\Local\Temp\claude\e--Dropbox-GameDev-1-Projects-GRIDCOM\b6a543f0-cd49-48c1-9bbe-8491444939cc\scratchpad'
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'voltage_reactive_verify.png')
pygame.image.save(display_surf, out_path)
print(f'Saved: {out_path}')

# Also render the selected GEN-1 unit's context panel (AVR setpoint, PV/PQ, Q reserve)
renderer.clear_selection()
renderer._selected_label = 'GEN-1'
sim.set_generator_voltage_setpoint('GEN-1', 0.995)
sim.tick(1.0)
renderer.tick(0.016, state=sim.get_state(), speed_mult=0)
renderer.tick(0.016, state=sim.get_state(), speed_mult=0)
out_path2 = os.path.join(out_dir, 'voltage_reactive_verify_unit.png')
pygame.image.save(display_surf, out_path2)
print(f'Saved: {out_path2}')
