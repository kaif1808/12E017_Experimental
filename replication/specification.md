# Implementation Plan: Niederle & Vesterlund (2007) in oTree

**Paper:** "Do Women Shy Away from Competition? Do Men Compete Too Much?" *QJE* 122(3), 1067–1101.
**Target stack:** oTree 5.x (Python 3.10+), browser-based, deployable in-lab or remotely.
**Audience:** Future coding agents extending or executing this build.

---

## 1. Project structure

```
nv2007/
├── settings.py                  # SESSION_CONFIGS, ROOMS, currency = USD
├── requirements.txt             # otree>=5.10
├── README.md                    # how to run, deploy, export
├── _static/global/              # any shared CSS
├── _templates/global/           # base.html with countdown/progress bar
└── nv2007/                      # the single app
    ├── __init__.py              # Constants, models, pages, page_sequence
    ├── pages/                   # one template per Page subclass
    │   ├── Welcome.html
    │   ├── Instructions1.html   # piece rate
    │   ├── Task1.html           # 5-min add task
    │   ├── Results1.html        # show absolute score
    │   ├── Instructions2.html   # tournament
    │   ├── Task2.html
    │   ├── Results2.html
    │   ├── Instructions3.html   # choice + perform
    │   ├── Choice3.html
    │   ├── Task3.html
    │   ├── Instructions4.html   # choice for past performance
    │   ├── Choice4.html
    │   ├── Beliefs.html         # rank guesses for Task 1 & Task 2
    │   ├── PaymentDraw.html     # show which task pays
    │   └── Results.html         # final reveal + payoff
    └── tests.py                 # bots for the full sequence
```

Use **one app** (`nv2007`). All four tasks live in the same app so `player` carries scores across rounds without round-number gymnastics.

---

## 2. Constants (`Constants` / `C` class)

```python
class C(BaseConstants):
    NAME_IN_URL = 'nv2007'
    PLAYERS_PER_GROUP = 4         # exactly 2M + 2F — see §4 on grouping
    NUM_ROUNDS = 1                # single round; tasks are separate Pages
    TASK_SECONDS = 300            # 5 minutes per performance task
    PIECE_RATE = cu(0.50)
    TOURNAMENT_RATE = cu(2.00)
    BELIEF_PAYMENT = cu(1.00)     # per correct rank guess
    SHOWUP_FEE = cu(5.00)
    COMPLETION_FEE = cu(7.00)
    NUM_ADDENDS = 5               # five 2-digit numbers
    ADDEND_MIN = 10
    ADDEND_MAX = 99
    PROBLEMS_PER_TASK = 60        # generate plenty; participants won't finish all
```

Only **one** task is paid (drawn at end). `participant.payoff` = showup + completion + drawn-task earnings + belief earnings.

---

## 3. Data model

### Player fields
```python
gender = models.StringField(choices=[['M','Male'],['F','Female']])  # collected at Welcome
score1 = models.IntegerField(initial=0)   # Task 1 correct count
score2 = models.IntegerField(initial=0)   # Task 2
score3 = models.IntegerField(initial=0)   # Task 3
choice3 = models.StringField(choices=[['piece','Piece rate'],['tour','Tournament']])
choice4 = models.StringField(choices=[['piece','Piece rate'],['tour','Tournament']])
belief_rank1 = models.IntegerField(min=1, max=4)
belief_rank2 = models.IntegerField(min=1, max=4)
paid_task = models.IntegerField()         # 1–4, set by set_payoffs
task_earnings = models.CurrencyField()
won_tournament3 = models.BooleanField(initial=False)
won_tournament4 = models.BooleanField(initial=False)
```

### Per-problem tracking (subsession-level)
Store every attempt — task number, problem index, addends, submitted answer, correct, timestamp — in an `ExtraModel` (`Attempt`) so we can audit speed and accuracy:

```python
class Attempt(ExtraModel):
    player = models.Link(Player)
    task = models.IntegerField()
    problem_idx = models.IntegerField()
    addends = models.StringField()        # JSON list
    correct_answer = models.IntegerField()
    submitted = models.IntegerField()
    is_correct = models.BooleanField()
    response_ms = models.IntegerField()
```

Export via `custom_export` for the analysis pipeline.

---

## 4. Grouping (the critical design constraint)

Groups must be **exactly 2M + 2F**. oTree's default grouping is sequential, which won't enforce composition. Approach:

1. Collect `gender` on the **Welcome** page (before grouping).
2. Use a `WaitPage` with `group_by_arrival_time=True` and a custom `group_by_arrival_time_method` in `Subsession`:

```python
def group_by_arrival_time_method(subsession, waiting_players):
    males   = [p for p in waiting_players if p.gender == 'M']
    females = [p for p in waiting_players if p.gender == 'F']
    if len(males) >= 2 and len(females) >= 2:
        return [males[0], males[1], females[0], females[1]]
    return None
```

Edge case: if a session ends with leftover unmatched participants, route them to a `Dropped` page that pays showup only. Document this in the pre-registration.

**In-lab variant:** if seating physically enforces 2M+2F per row, you can hardcode group IDs via session config and skip arrival-time grouping. Faster and more reliable. Prefer this when possible.

---

## 5. Page-by-page logic

| Page | Timeout | Notes |
|---|---|---|
| `Welcome` | none | Collect gender, consent. Explain "1 of 4 tasks paid". |
| `GroupingWaitPage` | — | `group_by_arrival_time=True`, custom method above. |
| `Instructions1` | none | Piece rate rules. Sample problem. |
| `Task1` | 300s hard | JS form: render problem, accept answer, show ✓/✗ + running tally, next problem. Submit aggregate score on timeout via `live_method` or hidden form. |
| `Results1` | none | Show `score1`. No relative info. |
| `Instructions2` | none | Tournament rules: highest of 4 wins $2/correct. |
| `Task2` | 300s | Same UI as Task 1. **No leaderboard.** |
| `Results2` | none | Show `score2` only. |
| `Instructions3` | none | Explain: choose scheme; if tournament, compared vs groupmates' **Task-2** scores. |
| `Choice3` | none | Radio: piece / tournament → `choice3`. |
| `Task3` | 300s | Same task, 5 min. |
| `Instructions4` | none | Explain: choose scheme applied to **Task-1** score; if tournament, compared vs groupmates' **Task-1** scores. |
| `Choice4` | none | Radio → `choice4`. No new performance. |
| `Beliefs` | none | Two integer inputs (1–4) for `belief_rank1`, `belief_rank2`. |
| `ResultsWaitPage` | — | `after_all_players_arrive = set_payoffs` (group-level). |
| `Results` | none | Reveal ranks, drawn task, payoffs. |

**Critical ordering rule (from guide §6):** beliefs come **after** all four tasks. Don't move them.

---

## 6. The addition task UI

Build as a single self-contained template with a small JS controller. Rationale: hitting the server for each problem adds latency that contaminates the 5-minute window. Use oTree's `live_method` to stream submissions, or batch them and POST on timeout.

### Recommended approach: `live_method`
- Server pre-generates a list of `PROBLEMS_PER_TASK` problems for the player at task start (deterministic seed = `participant.code + task_num` for reproducibility).
- JS pulls problem N, displays addends stacked vertically, accepts integer input, posts `{task, idx, answer, response_ms}` via `liveSend`.
- Server validates, increments `score{N}`, writes an `Attempt`, returns `{correct: bool, total: int, next_problem: {...}}`.
- On `TASK_SECONDS` timeout, JS auto-submits the page.

### UI requirements
- Large monospace addends, right-aligned.
- Visible countdown timer (use oTree's built-in `{{ formfield_with_countdown }}` or custom JS reading `Page.timeout_seconds`).
- Running tally of correct answers (per guide §3 Task 1).
- **No** indication of others' progress, ever.
- Disable browser back button (oTree handles via page sequence).
- No calculator: instruct verbally + add CSS to discourage copy-paste of problem text (cosmetic only).

---

## 7. Payoff calculation (`set_payoffs`)

Run on the `ResultsWaitPage` after Beliefs. Group-level method:

```python
def set_payoffs(group):
    players = group.get_players()
    # Determine winners for each tournament context
    max_t2 = max(p.score2 for p in players)
    t2_winners = [p for p in players if p.score2 == max_t2]
    # Task 3: each tournament-chooser compared vs groupmates' Task-2 scores
    # Task 4: each tournament-chooser compared vs groupmates' Task-1 scores
    for p in players:
        # Task 3 win: own score3 > all OTHER groupmates' score2
        others_t2 = [o.score2 for o in players if o != p]
        p.won_tournament3 = (p.choice3 == 'tour') and (p.score3 > max(others_t2))
        others_t1 = [o.score1 for o in players if o != p]
        p.won_tournament4 = (p.choice4 == 'tour') and (p.score1 > max(others_t1))
        # Random task draw
        p.paid_task = random.randint(1, 4)
        p.task_earnings = compute_task_earnings(p, t2_winners)
        # Belief bonuses
        belief_bonus = belief_payoff(p, players)
        p.payoff = (C.SHOWUP_FEE + C.COMPLETION_FEE
                    + p.task_earnings + belief_bonus)
```

**Tie-breaking:** ties broken randomly per guide §3. For Task 2 with multiple `t2_winners`, if the participant is among them, pick one at random with equal probability.

**Important nuance:** Task-3 tournament compares against groupmates' **Task-2** scores (per guide §3 Task 3 + §6). Task-4 tournament compares against groupmates' **Task-1** scores. Task-2 tournament compares against groupmates' **Task-2** scores (within-task). Don't confuse these — write the comparator function with explicit task arguments and unit-test it.

---

## 8. Belief elicitation

Two integer inputs, 1–4, one for Task-1 rank and one for Task-2 rank within the group. Pay $1 per correct guess. **Generous tie handling** (guide §4): if the player tied with k others at rank r, any guess in `[r, r+k-1]` (or however ranks are conventionally assigned with ties) counts as correct. Decide one convention and document it.

Recommended: assign **competition ranking** (1224). A player tied for 2nd in a group where two players score higher than them and one below would correctly guess 3 (since two are ranked 1st-tied). Easier rule and matches the "any rank that could be correct" spirit: if multiple players share the same score, accept any rank within the tied block.

---

## 9. Randomization & reproducibility

- Seed the addition-problem generator with `(participant.code, task_num)` so any rerun produces identical problems for that participant. Store the seed in `participant.vars` for audit.
- Seed the random task draw with `participant.code` so payment is verifiable post-hoc.
- Log all RNG calls.

---

## 10. Session config

```python
SESSION_CONFIGS = [
    dict(
        name='nv2007_lab',
        display_name='Niederle & Vesterlund 2007 (Lab)',
        num_demo_participants=4,
        app_sequence=['nv2007'],
        use_browser_bots=False,
    ),
    dict(
        name='nv2007_pilot',
        display_name='NV 2007 — Pilot (bots)',
        num_demo_participants=8,
        app_sequence=['nv2007'],
        use_browser_bots=True,
    ),
]
PARTICIPANT_FIELDS = []
SESSION_FIELDS = []
REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = False
ROOMS = [dict(name='econ_lab', display_name='Econ Lab', participant_label_file='_rooms/lab.txt')]
```

For lab use, create `_rooms/lab.txt` with one participant label per line (e.g., `seat_01`...`seat_80`).

---

## 11. Testing (`tests.py`)

Bots must walk the full sequence and exercise edge cases:

- **Bot 1:** Male, high performer, picks tournament both times, guesses rank 1.
- **Bot 2:** Female, mid performer, picks piece rate both times.
- **Bot 3:** Tied scores with another bot — exercises tie-breaking.
- **Bot 4:** Submits wrong answers, tests scoring.

Run: `otree test nv2007 --num-participants=4`.

Add `pytest` unit tests for:
- `set_payoffs` with hand-constructed score arrays.
- Tournament comparators (Task 2/3/4 each).
- Belief payoff with ties.
- Problem generator determinism given seed.

---

## 12. Data export

Implement `custom_export(players)` to produce a long-format CSV with one row per `Attempt` joined to player covariates (gender, all scores, choices, beliefs, paid_task, payoffs). This is the analysis-ready file.

Also export a wide one-row-per-player CSV for the headline regressions in §13.

---

## 13. Pre-registered analysis (mirror guide §7)

Code in `analysis/` (separate from oTree app), in R or Python:

1. **Primary:** Fisher's exact test on `choice3 == 'tour'` by `gender`. Hypothesis: male entry > female entry.
2. **Probit 1:** `choice3 ~ female + score2 + (score2 - score1)`. Marginal effects at score2=13, score1=12.
3. **Probit 2:** add `belief_rank2` (recoded so higher = more confident, e.g., `5 - belief_rank2`).
4. **Probit 3:** add `choice4` dummy.
5. **Task-4 probit:** `choice4 ~ female + score1 + belief_rank1`. Test: female coefficient → 0.
6. Decomposition table: report female marginal effect at each step, mirroring the 38 → 28 → 16 pp cascade.

Pre-register on AsPredicted before any data collection. Lock the sample size (≥30 groups = N≥120 recommended; original 20 groups was underpowered).

---

## 14. Deployment

### Local lab
```
pip install -r requirements.txt
otree devserver        # development
otree prodserver 8000  # production, behind nginx
```

### Remote (Heroku / Render / Railway)
- oTree's standard Heroku deploy works. Use Postgres add-on.
- Set `OTREE_PRODUCTION=1`, `OTREE_ADMIN_PASSWORD`, `OTREE_AUTH_LEVEL=STUDY`.
- For Prolific recruitment, use oTree Rooms with `participant_label_file` mapped to Prolific IDs, and append `?participant_label={{%PROLIFIC_PID%}}` to the study URL.

### Online adaptation caveat (guide §8)
Online removes the visual gender cue. You must **explicitly tell participants their group composition** ("you are in a group of 2 men and 2 women") for the design to remain comparable. This is a deviation from the original — flag it in pre-registration and discussion.

---

## 15. IRB & ethics

- Standard exempt/expedited review; no deception.
- Consent form on Welcome page, with a checkbox before Continue is enabled.
- Debrief page at end explains the original study and links to the paper.
- Pay via lab cash (in-lab) or platform payment (Prolific bonus).
- Do not collect identifying info beyond what the platform requires.

---

## 16. Pitfalls checklist (from guide §8)

- [ ] N ≥ 120 (30 groups), not the original 80.
- [ ] Problem difficulty piloted; median ~10–15 correct in 5 min in your population.
- [ ] No mention of gender, competition, or hypothesis in instructions.
- [ ] Beliefs elicited **after** all four tasks.
- [ ] Exactly one task paid, drawn at the end.
- [ ] Task-3 comparison is vs groupmates' **Task-2** scores (not Task-3).
- [ ] Task-4 comparison is vs groupmates' **Task-1** scores.
- [ ] No relative-performance feedback until after Beliefs.
- [ ] Tie-breaking rule documented and consistent.

---

## 17. Build order for the implementing agent

1. Scaffold project (`otree startproject nv2007 && otree startapp nv2007`).
2. Implement `Constants`, `Player`, `Group`, `Subsession`, `Attempt` ExtraModel.
3. Build `Task1` page end-to-end (problem generator + live_method + scoring) and bot-test it. **Get this right before duplicating.**
4. Duplicate task page logic for Tasks 2 and 3; add tournament payoff stubs.
5. Add `Choice3`, `Choice4`, `Beliefs`.
6. Implement `set_payoffs` with unit tests.
7. Build `Welcome` (gender + consent) and arrival-time grouping.
8. Wire `page_sequence`.
9. Write bot tests covering all branches.
10. `custom_export` and analysis scripts.
11. Pilot with 4–8 colleagues, calibrate problem difficulty.
12. Pre-register, then run.

---

**Reference:** Niederle, M. & Vesterlund, L. (2007). *QJE* 122(3), 1067–1101.