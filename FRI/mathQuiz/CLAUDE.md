# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run application
python main.py                   # Default 10-minute quiz
python main.py --duration 300    # 5-minute quiz
./run_quiz.sh [duration_seconds] # Alternative launcher with auto-venv activation
```

No test suite is configured. Testing is manual.

## Architecture

**Math Quiz Application** - An adaptive PyQt6-based math quiz with Khan Academy-inspired difficulty adjustment, LaTeX rendering, and multiple mathematical domains.

### Core Components

```
main.py                  Entry point, PyQt6 app initialization
quiz/
  engine.py              QuizEngine orchestrator - coordinates all subsystems
  difficulty.py          Adaptive difficulty (sliding window, streak bonuses)
  scoring.py             Power-test scoring with difficulty multipliers
  answer_parser.py       Safe SymPy-based parsing (no eval())
  questions/
    base.py              Question dataclass + QuestionGenerator abstract base
    [category].py        Individual question generators (calculus, algebra, etc.)
ui/
  main_window.py         Primary GUI, timer, preferences dialog
  latex_label.py         LaTeX-to-QPixmap rendering
  plot_widget.py         Matplotlib figure embedding
  summary_dialog.py      Session completion analytics
utils/
  settings.py            JSON-based preferences (~/.config/mathquiz/)
  symbolic.py            SymPy wrapper with optional Maxima integration
```

### Key Patterns

- **Adaptive Difficulty**: `DifficultyManager` tracks last 5 answers. 80%+ correct → increase level, 40%- → decrease. 3-streak bonuses for rapid jumps.
- **Safe Parsing**: `AnswerParser` uses SymPy's `sympify()` with restricted namespace instead of `eval()`.
- **Question Factory**: Each category inherits `QuestionGenerator`, implements `generate(difficulty)`, returns `Question` dataclass.
- **UI Callbacks**: Engine notifies UI of state changes via registered callbacks.

### Adding New Question Types

1. Create `quiz/questions/new_category.py` inheriting from `QuestionGenerator`
2. Implement `generate(difficulty)` returning a `Question` object
3. Set `CATEGORY` and `DIFFICULTY_RANGE` class attributes
4. Register in `QuizEngine.QUESTION_FACTORIES` dict (`engine.py`)
5. Add settings toggle in `PreferencesDialog` if user-controllable

### Question Categories

Calculus, Algebra, Physics, Estimation, Linear Algebra, Statistics, Accounting, Graphical (plot-based). Each supports difficulty levels 1-5 (VERY_EASY to VERY_HARD) within their defined range.

### Scoring

Base points scale by difficulty (5→50 pts). Wrong answers incur penalties. Trivial answers on hard questions get extra penalty. Estimation questions support partial credit based on accuracy ratio.
