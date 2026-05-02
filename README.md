# AI Day Planner

Predictive day-planner with fatigue modeling. Python/FastAPI backend, SQLite storage, offline-first.

**See [INSTRUCTIONS.md](INSTRUCTIONS.md) for installation and startup.**

---

## What it does

- Manages tasks with difficulty, urgency, importance, and estimated duration
- Maintains a weekly calendar with immutable time blocks
- Schedules tasks into free slots based on priority score and fatigue
- Tracks actual time spent (including interruptions) and learns correction coefficients via EMA
- Models completion probability per task/slot; blocks low-probability assignments
- Emits structured events on an in-process bus for decoupled module communication

## Architecture

Modular monolith. All domain logic as pure functions. Config injected everywhere. No hardcoded values.

```
FastAPI app
└── /api/v1/
    ├── /tasks
    ├── /calendar
    ├── /schedule
    ├── /fatigue
    ├── /tracking
    ├── /learning
    ├── /probability
    └── /config
```

Modules communicate only through the event bus (`task_tracked`, `fatigue_updated`, `coefficient_updated`, etc.).
