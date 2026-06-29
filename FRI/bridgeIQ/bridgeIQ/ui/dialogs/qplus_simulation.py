"""
Q-Plus style simulation dialog.

NOTE: The upstream commit that wired up ``QPlusSimulationDialog``
(imported by ``ui/dialogs/__init__.py`` and ``ui/main_window.py``)
did not actually commit this module, so a fresh clone crashes at
startup with ``No module named 'ui.dialogs.qplus_simulation'``.

The two call sites in ``main_window.py`` construct it with the same
signature as :class:`SimulationDialog` —
``QPlusSimulationDialog(engine, board, seat, parent)`` followed by
``.exec()`` — so until the real Q-Plus styled dialog is committed we
alias it to the working :class:`SimulationDialog`. This keeps the
"Q-Plus simulation" menu entry and the slam-opportunity auto-popup
functional instead of failing to launch.
"""

from .simulation import SimulationDialog


class QPlusSimulationDialog(SimulationDialog):
    """Alias of :class:`SimulationDialog` (see module docstring)."""
    pass


__all__ = ["QPlusSimulationDialog"]
