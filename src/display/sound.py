"""
src/display/sound.py

SoundManager: plays the alarm loop and info/tutor ping in response to the
Alarm list on SimulationState.active_alarms. Owned and driven once per
frame by Renderer.tick().
"""

from __future__ import annotations

import pygame

from simulation.constants import (
    SOUND_PATH_ALARM, SOUND_PATH_PING,
    SOUND_VOLUME_ALARM, SOUND_VOLUME_PING,
)
from utils.helpers import resource_path

_ALARM_PRIORITIES = ('WARNING', 'CRITICAL')


def _load_sound(relative_path: str, volume: float) -> pygame.mixer.Sound | None:
    path = resource_path(relative_path)
    if not path.exists():
        return None
    sound = pygame.mixer.Sound(str(path))
    sound.set_volume(volume)
    return sound


class SoundManager:
    """Drives the alarm loop channel and one-shot info/tutor pings."""

    def __init__(self) -> None:
        self._alarm_sound = _load_sound(SOUND_PATH_ALARM, SOUND_VOLUME_ALARM)
        self._ping_sound  = _load_sound(SOUND_PATH_PING, SOUND_VOLUME_PING)

        self._alarm_channel: pygame.mixer.Channel | None = None
        if pygame.mixer.get_init():
            # Reserve channel 0 for the alarm loop so Sound.play()'s
            # auto-allocation (used by the ping) can never steal it.
            pygame.mixer.set_reserved(1)
            self._alarm_channel = pygame.mixer.Channel(0)

        self._last_seen_alarm_id: int = -1
        self._silenced: bool = False

    def update(self, active_alarms: list) -> None:
        """Call once per rendered frame with the current SimulationState.active_alarms."""
        new_max_id = self._last_seen_alarm_id
        for alarm in active_alarms:
            if alarm.alarm_id <= self._last_seen_alarm_id:
                continue
            new_max_id = max(new_max_id, alarm.alarm_id)
            if alarm.priority in _ALARM_PRIORITIES:
                self._silenced = False
            elif self._ping_sound is not None:
                self._ping_sound.play()
        self._last_seen_alarm_id = new_max_id

        alarm_active = any(
            a.priority in _ALARM_PRIORITIES and not a.acknowledged
            for a in active_alarms
        )

        if self._alarm_channel is None:
            return

        if alarm_active and not self._silenced:
            if not self._alarm_channel.get_busy() and self._alarm_sound is not None:
                self._alarm_channel.play(self._alarm_sound, loops=-1)
        else:
            if self._alarm_channel.get_busy():
                self._alarm_channel.stop()
            if not alarm_active:
                self._silenced = False

    def silence(self) -> None:
        """Stop the alarm loop until a new WARNING/CRITICAL alarm is raised."""
        self._silenced = True
        if self._alarm_channel is not None:
            self._alarm_channel.stop()
