# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

oTree 5.x replication of Niederle & Vesterlund (2007), *Do Women Shy Away from Competition?* The experiment has four tasks (piece rate, tournament, choice+perform, choice for past performance) and elicits beliefs about relative rank. Only one randomly drawn task is paid. Groups must be exactly 2M + 2F.

## Stack

- **oTree 5.x** (Python 3.10+), single app `nv2007`
- **Analysis** in `analysis/` (R or Python), separate from the oTree app

## Commands

```bash
# Install
pip install -r requirements.txt

# Development server
otree devserver

# Production server (behind nginx)
otree prodserver 8000

# Run browser-bot tests (requires 4 participants)
otree test nv2007 --num-participants=4

# Run pytest unit tests (payoff logic, generators, etc.)
pytest analysis/
```

## Architecture

The entire experiment lives in **one app** (`nv2007/`) so `player` fields carry scores across all four tasks without round gymnastics. Key design decisions:

### Data model
- `Player` holds all four scores (`score1`–`score3`), choices (`choice3`, `choice4`), beliefs (`belief_rank1`, `belief_rank2`), and payoff fields.
- `Attempt` ExtraModel stores every individual problem submission (task, index, addends, answer, correctness, response time) for the audit trail. Exported via `custom_export`.

### Task UI (`live_method` pattern)
Each task page pre-generates `PROBLEMS_PER_TASK` problems server-side seeded by `(participant.code, task_num)` for reproducibility. JS sends each answer via `liveSend`; server validates, increments `scoreN`, writes an `Attempt`, returns correctness + next problem. Page auto-submits on the 300s timeout.

### Grouping constraint
The `GroupingWaitPage` uses `group_by_arrival_time=True` with a custom `group_by_arrival_time_method` that only forms groups when ≥2 males and ≥2 females are waiting. Gender is collected on the Welcome page before grouping. In-lab variant: hardcode group IDs via session config to bypass arrival-time grouping.

### Payoff calculation (`set_payoffs`)
Runs on `ResultsWaitPage` after Beliefs. Critical comparator rules:
- Task 2 tournament: own `score2` vs groupmates' `score2`
- Task 3 tournament: own `score3` vs groupmates' **`score2`** (not score3)
- Task 4 tournament: own `score1` vs groupmates' **`score1`**
- Paid task drawn randomly per participant; seed with `participant.code` for auditability.

### Belief payoff
Uses competition ranking (1224). Ties accepted if the guess falls within the tied block. Pays `C.BELIEF_PAYMENT` ($1) per correct rank.

### Page sequence
`Welcome → GroupingWaitPage → Instructions1 → Task1 → Results1 → Instructions2 → Task2 → Results2 → Instructions3 → Choice3 → Task3 → Instructions4 → Choice4 → Beliefs → ResultsWaitPage → Results`

Beliefs **must** come after all four tasks and before `ResultsWaitPage`.

## Critical pitfalls

- Task-3 comparison is vs groupmates' **Task-2** scores (not Task-3). Task-4 comparison is vs groupmates' **Task-1** scores. These are easy to mix up — write the comparator with explicit task arguments and unit-test each case.
- No relative-performance feedback shown until after Beliefs page.
- Tie-breaking must be consistent; document the chosen convention.
- `set_payoffs` runs once at group level; do not call it per-player.

## Build order (from specification)

1. Scaffold → implement models (`Constants`, `Player`, `Group`, `Subsession`, `Attempt`)
2. Build Task1 end-to-end (problem generator + live_method + scoring) and bot-test before duplicating
3. Duplicate for Tasks 2 & 3; add tournament payoff stubs
4. Add Choice3, Choice4, Beliefs pages
5. Implement `set_payoffs` with pytest unit tests
6. Welcome page + arrival-time grouping
7. Wire `page_sequence`; full bot test suite
8. `custom_export` and analysis scripts in `analysis/`

## Deployment env vars

```
OTREE_PRODUCTION=1
OTREE_ADMIN_PASSWORD=<secret>
OTREE_AUTH_LEVEL=STUDY
```
