
---

# 🔧 SYSTEM DESIGN OVERVIEW

## Core Idea

A **predictive day-planner with fatigue modeling**, where:

- user input is primary
    
- system learns correction factors
    
- scheduling is semi-automatic
    
- focus = maximize task completion without burnout
    

---

# 🧠 CORE COMPONENTS

## 1. Task System

Entities:

### Task

```
id
title
description_md
difficulty (1–5)
estimated_time_minutes (user input)
corrected_time_minutes (system)
importance (1–5)
urgency (1–5)
deadline (optional)
is_immutable (bool)
is_emergency (bool)
is_locked (bool)
type (one-time | recurring | long-term | no_date)
dependencies (list of task_ids)
tags[]
attachments[]
subtasks[]
completion_status
created_at
updated_at
```

---

### TaskExecution (for learning)

```
task_id
start_time
end_time
breaks_duration
interruptions_count
actual_duration
completed (bool)
fatigue_at_start
fatigue_at_end
```

---

### Goal

```
id
title
target_value (optional)
current_progress
deadline
tasks[]
```

---

### TimeBlock

```
start_time
end_time
type (immutable | scheduled | free)
task_id (optional)
```

---

### FatigueState

```
timestamp
fatigue_score (1–100)
fatigue_level (1–5)
```

---

## 2. Fatigue Model

### Base Model

```
fatigue(t) = fatigue_prev 
           + work_load_factor 
           - recovery_factor
```

---

### Work Load Factor

```
work_load = Σ(task_difficulty × time_spent × weight)
```

---

### Recovery

- dynamic (learned)
    
- initial:
    

```
recovery_per_hour_rest = 5
recovery_sleep = 30–50
```

---

### Levels

```
1–20   → very low
21–40  → low
41–60  → medium
61–80  → high
81–100 → critical
```

---

### Effects

- max tasks/day
    
- allowed difficulty
    
- probability penalty
    

---

## 3. Time Estimation Learning

### Correction Coefficient

Grouped buckets:

```
0–60 min
60–240 min
240–480 min
```

For each:

```
correction_coef = avg(actual_time / estimated_time)
```

Then:

```
corrected_time = estimated_time × coef
```

---

## 4. Scheduling Engine

### Priority Score

```
score = 
  (urgency × 0.4) +
  (importance × 0.3) +
  (deadline_proximity × 0.2) +
  (duration_weight × 0.1)
```

---

### Constraints

- immutable blocks fixed
    
- locked tasks immovable
    
- emergency tasks override everything
    

---

### Scheduling Flow

1. Fill immutable blocks
    
2. Insert locked tasks
    
3. Insert urgent tasks
    
4. Fill remaining slots:
    
    - respect fatigue
        
    - maximize completion probability
        
    - include no_date tasks if space
        

---

## 5. Probability Model

Initial:

```
P = base 
  - fatigue_penalty 
  - duration_penalty 
  + historical_success_rate
```

Block scheduling if:

```
P < 0.35 (unless overridden)
```

---

## 6. Interruptions

- manual input
    
- task pauses
    
- data logged
    
- used for learning
    

---

## 7. Weekly Optimization

System ensures:

- ≥1–2 rest days
    
- ≥75% task completion probability
    
- urgent tasks scheduled
    
- big tasks distributed
    

---

## 8. UI STRUCTURE

### Main View

- weekly calendar
    
- heatmap (load)
    
- fatigue graph
    
- task list (day + backlog)
    
- goals panel
    

---

### Task Card

- markdown
    
- subtasks
    
- dependencies
    
- attachments
    
- execution logs
    

---

# ⚙️ ARCHITECTURE

## Style

- modular monolith
    

---

## Backend (Python)

- FastAPI
    
- local-first
    
- event layer for AI
    

---

## DB

- SQLite (local)
    
- optional sync later
    

---

## Modules

```
/core
  /tasks
  /scheduler
  /fatigue
  /prediction
  /learning

/api
/ui
/storage
```

---

# 🚫 STRICT CODING RULES (IMPORTANT)

Include these EXACTLY in your AI prompt:

- NO hardcoded values (except clearly marked constants)
    
- ALL logic modularized
    
- EVERY feature must have tests
    
- NO hidden state
    
- ALL models typed
    
- PURE functions for calculations
    
- SEPARATE:
    
    - logic
        
    - storage
        
    - API
        
- ALL coefficients configurable
    
- NO magic numbers
    
- LOG all decisions (for debugging learning system)
    

---

# 🧪 TESTING REQUIREMENTS

- unit tests for:
    
    - scheduling
        
    - fatigue updates
        
    - time correction
        
- simulation tests:
    
    - full week scheduling
        
    - interruptions
        
- edge cases:
    
    - overload
        
    - emergency override
        
    - zero free time
        

---

