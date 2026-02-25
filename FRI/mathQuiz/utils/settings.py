"""
Application settings management.

Handles loading and saving user preferences.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


class Settings:
    """
    Manages application settings with persistence.

    Settings are stored in a JSON file in the user's config directory.
    """

    # Default settings
    DEFAULTS = {
        'include_physics': True,  # Physics (Hard/Very Hard) - on by default
        'include_estimation': True,
        'include_linear_algebra': True,  # Advanced: No BS Linear Algebra (on by default)
        'include_statistics': True,  # Advanced: No BS Statistics (on by default)
        'include_accounting': True,  # Advanced: Accounting for CS (on by default)
        'session_duration': 600,  # 10 minutes
        'starting_difficulty': 'easy',
    }

    def __init__(self):
        self._settings: Dict[str, Any] = self.DEFAULTS.copy()
        self._config_path = self._get_config_path()
        self.load()

    def _get_config_path(self) -> Path:
        """Get the path to the config file."""
        config_dir = Path.home() / '.config' / 'mathquiz'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'settings.json'

    def load(self) -> None:
        """Load settings from disk."""
        if self._config_path.exists():
            try:
                with open(self._config_path, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults (in case new settings added)
                    self._settings = {**self.DEFAULTS, **loaded}
            except (json.JSONDecodeError, IOError):
                self._settings = self.DEFAULTS.copy()
        else:
            self._settings = self.DEFAULTS.copy()

    def save(self) -> None:
        """Save settings to disk."""
        try:
            with open(self._config_path, 'w') as f:
                json.dump(self._settings, f, indent=2)
        except IOError:
            pass  # Silently fail if can't save

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save."""
        self._settings[key] = value
        self.save()

    @property
    def include_physics(self) -> bool:
        """Whether to include physics questions."""
        return self._settings.get('include_physics', False)

    @include_physics.setter
    def include_physics(self, value: bool) -> None:
        self.set('include_physics', value)

    @property
    def include_estimation(self) -> bool:
        """Whether to include estimation questions."""
        return self._settings.get('include_estimation', True)

    @include_estimation.setter
    def include_estimation(self, value: bool) -> None:
        self.set('include_estimation', value)

    @property
    def session_duration(self) -> int:
        """Session duration in seconds."""
        return self._settings.get('session_duration', 600)

    @session_duration.setter
    def session_duration(self, value: int) -> None:
        self.set('session_duration', value)

    @property
    def include_linear_algebra(self) -> bool:
        """Whether to include linear algebra questions (No BS Linear Algebra)."""
        return self._settings.get('include_linear_algebra', False)

    @include_linear_algebra.setter
    def include_linear_algebra(self, value: bool) -> None:
        self.set('include_linear_algebra', value)

    @property
    def include_statistics(self) -> bool:
        """Whether to include statistics questions (No BS Statistics)."""
        return self._settings.get('include_statistics', False)

    @include_statistics.setter
    def include_statistics(self, value: bool) -> None:
        self.set('include_statistics', value)

    @property
    def include_accounting(self) -> bool:
        """Whether to include accounting questions (Accounting for CS)."""
        return self._settings.get('include_accounting', False)

    @include_accounting.setter
    def include_accounting(self, value: bool) -> None:
        self.set('include_accounting', value)


# Global settings instance
settings = Settings()
