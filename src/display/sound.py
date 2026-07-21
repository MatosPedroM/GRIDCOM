"""
src/display/sound.py

SoundManager: drives two independent severity loops (alarm.wav while any
CRITICAL alarm is unacknowledged, warning_ping.wav while any WARNING alarm
is unacknowledged) plus a one-shot ping.wav for new INFO/TUTOR alarms, in
response to the Alarm list on SimulationState.active_alarms. Owned and
driven once per frame by Renderer.tick().
"""

from __future__ import annotations

import pygame

from simulation.constants import (
    SOUND_PATH_ALARM, SOUND_PATH_PING, SOUND_PATH_WARNING_PING,
    SOUND_VOLUME_ALARM, SOUND_VOLUME_PING, SOUND_VOLUME_WARNING_PING,
)
from utils.helpers import resource_path


def _load_sound(relative_path: str, volume: float) -> pygame.mixer.Sound | None:
    path = resource_path(relative_path)
    if not path.exists():
        return None
    sound = pygame.mixer.Sound(str(path))
    sound.set_volume(volume)
    return sound


class SoundManager:
    """Drives the CRITICAL/WARNING loop channels and the one-shot INFO/TUTOR ping."""

    def __init__(self) -> None:
        self._alarm_sound = _load_sound(SOUND_PATH_ALARM, SOUND_VOLUME_ALARM)
        self._ping_sound  = _load_sound(SOUND_PATH_PING, SOUND_VOLUME_PING)
        self._warning_ping_sound = _load_sound(SOUND_PATH_WARNING_PING, SOUND_VOLUME_WARNING_PING)

        self._critical_channel: pygame.mixer.Channel | None = None
        self._warning_channel: pygame.mixer.Channel | None = None
        if pygame.mixer.get_init():
            # Reserve channels 0-1 for the two severity loops so Sound.play()'s
            # auto-allocation (used by the INFO/TUTOR ping) can never steal them.
            pygame.mixer.set_reserved(2)
            self._critical_channel = pygame.mixer.Channel(0)
            self._warning_channel  = pygame.mixer.Channel(1)

        self._last_seen_alarm_id: int = -1
        self._silenced: bool = False

    def update(self, active_alarms: list) -> None:
        """Call once per rendered frame with the current SimulationState.active_alarms."""
        new_max_id = self._last_seen_alarm_id
        for alarm in active_alarms:
            if alarm.alarm_id <= self._last_seen_alarm_id:
                continue
            new_max_id = max(new_max_id, alarm.alarm_id)
            if alarm.priority in ('WARNING', 'CRITICAL'):
                self._silenced = False
            elif self._ping_sound is not None:
                self._ping_sound.play()
        self._last_seen_alarm_id = new_max_id

        critical_active = any(a.priority == 'CRITICAL' and not a.acknowledged for a in active_alarms)
        warning_active  = any(a.priority == 'WARNING'  and not a.acknowledged for a in active_alarms)

        if self._critical_channel is not None:
            if critical_active and not self._silenced:
                if not self._critical_channel.get_busy() and self._alarm_sound is not None:
                    self._critical_channel.play(self._alarm_sound, loops=-1)
            elif self._critical_channel.get_busy():
                self._critical_channel.stop()

        if self._warning_channel is not None:
            if warning_active and not self._silenced:
                if not self._warning_channel.get_busy() and self._warning_ping_sound is not None:
                    self._warning_channel.play(self._warning_ping_sound, loops=-1)
            elif self._warning_channel.get_busy():
                self._warning_channel.stop()

        if not (critical_active or warning_active):
            self._silenced = False

    def silence(self) -> None:
        """Stop both severity loops until a new WARNING/CRITICAL alarm is raised."""
        self._silenced = True
        if self._critical_channel is not None:
            self._critical_channel.stop()
        if self._warning_channel is not None:
            self._warning_channel.stop()
