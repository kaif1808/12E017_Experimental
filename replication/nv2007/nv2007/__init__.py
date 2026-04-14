import json
import random

from otree.api import (
    BaseConstants,
    BaseGroup,
    BasePlayer,
    BaseSubsession,
    ExtraModel,
    Page,
    WaitPage,
    cu,
    models,
)

doc = """
Replication of Niederle & Vesterlund (2007), "Do Women Shy Away from Competition?"
QJE 122(3), 1067–1101.

Four tasks: piece rate, tournament, choice+perform, choice for past performance.
Groups must be exactly 2M + 2F. Only one randomly drawn task is paid.
"""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class C(BaseConstants):
    NAME_IN_URL = 'nv2007'
    PLAYERS_PER_GROUP = 4       # exactly 2M + 2F
    NUM_ROUNDS = 1

    TASK_SECONDS = 300          # 5 minutes per performance task

    PIECE_RATE = cu(0.50)
    TOURNAMENT_RATE = cu(2.00)
    BELIEF_PAYMENT = cu(1.00)   # per correct rank guess
    SHOWUP_FEE = cu(5.00)
    COMPLETION_FEE = cu(7.00)

    NUM_ADDENDS = 5             # five 2-digit numbers per problem
    ADDEND_MIN = 10
    ADDEND_MAX = 99
    PROBLEMS_PER_TASK = 60      # generate plenty; participants won't finish all


# ---------------------------------------------------------------------------
# Extra model: per-problem audit trail
# ---------------------------------------------------------------------------

class Attempt(ExtraModel):
    player = models.Link(BasePlayer)
    task = models.IntegerField()
    problem_idx = models.IntegerField()
    addends = models.StringField()      # JSON list of ints
    correct_answer = models.IntegerField()
    submitted = models.IntegerField()
    is_correct = models.BooleanField()
    response_ms = models.IntegerField()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Subsession(BaseSubsession):
    pass


def group_by_arrival_time_method(subsession, waiting_players):
    """Only form a group when ≥2 males and ≥2 females are waiting."""
    males = [p for p in waiting_players if p.gender == 'M']
    females = [p for p in waiting_players if p.gender == 'F']
    if len(males) >= 2 and len(females) >= 2:
        return [males[0], males[1], females[0], females[1]]
    return None


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    gender = models.StringField(
        choices=[['M', 'Male'], ['F', 'Female']],
        label='What is your gender?',
    )
    consent = models.BooleanField(
        label='I have read and understood the above information and I consent to participate.',
        widget=models.widgets.CheckboxInput,
    )

    # Task scores (correct answers)
    score1 = models.IntegerField(initial=0)
    score2 = models.IntegerField(initial=0)
    score3 = models.IntegerField(initial=0)

    # Choices (Tasks 3 and 4)
    choice3 = models.StringField(
        choices=[['piece', 'Piece rate ($0.50 per correct answer)'],
                 ['tour', 'Tournament ($2.00 per correct answer if you win)']],
        label='Choose your payment scheme for Task 3:',
        widget=models.widgets.RadioSelect,
    )
    choice4 = models.StringField(
        choices=[['piece', 'Piece rate ($0.50 per correct answer)'],
                 ['tour', 'Tournament ($2.00 per correct answer if your Task 1 score wins)']],
        label='Choose the payment scheme to apply to your Task 1 score:',
        widget=models.widgets.RadioSelect,
    )

    # Beliefs (rank guesses, 1–4)
    belief_rank1 = models.IntegerField(
        min=1, max=4,
        label='What do you think was your rank in Task 1? (1 = highest, 4 = lowest)',
    )
    belief_rank2 = models.IntegerField(
        min=1, max=4,
        label='What do you think was your rank in Task 2? (1 = highest, 4 = lowest)',
    )

    # Payoff fields
    paid_task = models.IntegerField()
    task_earnings = models.CurrencyField()
    won_tournament2 = models.BooleanField(initial=False)
    won_tournament3 = models.BooleanField(initial=False)
    won_tournament4 = models.BooleanField(initial=False)
    belief_bonus = models.CurrencyField(initial=cu(0))

    # Rank info (set in set_payoffs, shown on Results page)
    rank1 = models.IntegerField()
    rank2 = models.IntegerField()


# ---------------------------------------------------------------------------
# Problem generator
# ---------------------------------------------------------------------------

def generate_problems(participant_code, task_num, n=C.PROBLEMS_PER_TASK):
    """
    Deterministic problem list seeded by (participant_code, task_num).
    Returns a list of n sublists, each with C.NUM_ADDENDS 2-digit integers.
    """
    seed = hash((participant_code, task_num)) % (2 ** 32)
    rng = random.Random(seed)
    return [
        [rng.randint(C.ADDEND_MIN, C.ADDEND_MAX) for _ in range(C.NUM_ADDENDS)]
        for _ in range(n)
    ]


# ---------------------------------------------------------------------------
# Payoff helpers
# ---------------------------------------------------------------------------

def _competition_ranks(scores):
    """
    Assign competition ranks (1224 style).
    Returns a list of ranks in the same order as `scores`.
    """
    ranks = []
    for s in scores:
        rank = 1 + sum(1 for other in scores if other > s)
        ranks.append(rank)
    return ranks


def _belief_payoff(player, players):
    """
    Pay C.BELIEF_PAYMENT for each correct rank guess.
    Uses competition ranking (1224). A guess is correct if it falls within
    the tied block — i.e., if the true rank equals the competition rank
    assigned to the player (ties are handled by accepting any rank in the block).
    """
    scores1 = [p.score1 for p in players]
    scores2 = [p.score2 for p in players]
    ranks1 = _competition_ranks(scores1)
    ranks2 = _competition_ranks(scores2)

    idx = players.index(player)
    true_rank1 = ranks1[idx]
    true_rank2 = ranks2[idx]

    # Determine the size of the tied block for generous acceptance
    def tied_block_end(scores, true_rank):
        same_score = scores[[players.index(p) for p in players][players.index(player)]]
        # count players with same score
        tied_count = sum(1 for s in scores if s == same_score)
        return true_rank + tied_count - 1

    block_end1 = tied_block_end(scores1, true_rank1)
    block_end2 = tied_block_end(scores2, true_rank2)

    bonus = cu(0)
    if true_rank1 <= player.belief_rank1 <= block_end1:
        bonus += C.BELIEF_PAYMENT
    if true_rank2 <= player.belief_rank2 <= block_end2:
        bonus += C.BELIEF_PAYMENT
    return bonus


def _task2_winner(player, players):
    """
    Returns True if player wins the Task-2 tournament among groupmates.
    Ties broken randomly (seeded by participant.code for reproducibility).
    """
    max_score2 = max(p.score2 for p in players)
    if player.score2 < max_score2:
        return False
    winners = [p for p in players if p.score2 == max_score2]
    if len(winners) == 1:
        return True
    # random tie-break
    rng = random.Random(player.participant.code + '_t2')
    return rng.choice(winners) == player


def _compute_task_earnings(player, players):
    """
    Compute earnings for the randomly drawn paid task.
    """
    t = player.paid_task

    if t == 1:
        return player.score1 * C.PIECE_RATE

    elif t == 2:
        if _task2_winner(player, players):
            return player.score2 * C.TOURNAMENT_RATE
        return cu(0)

    elif t == 3:
        if player.choice3 == 'piece':
            return player.score3 * C.PIECE_RATE
        else:
            if player.won_tournament3:
                return player.score3 * C.TOURNAMENT_RATE
            return cu(0)

    else:  # t == 4
        if player.choice4 == 'piece':
            return player.score1 * C.PIECE_RATE
        else:
            if player.won_tournament4:
                return player.score1 * C.TOURNAMENT_RATE
            return cu(0)


def set_payoffs(group):
    """
    Run once at group level on ResultsWaitPage after Beliefs.

    Tournament comparator rules (critical — easy to mix up):
    - Task 2: own score2 vs groupmates' score2 (within-task)
    - Task 3: own score3 vs groupmates' score2 (not score3)
    - Task 4: own score1 vs groupmates' score1 (past performance)
    """
    players = group.get_players()

    # Compute competition ranks for display
    scores1 = [p.score1 for p in players]
    scores2 = [p.score2 for p in players]
    ranks1 = _competition_ranks(scores1)
    ranks2 = _competition_ranks(scores2)
    for i, p in enumerate(players):
        p.rank1 = ranks1[i]
        p.rank2 = ranks2[i]

    # Task-2 tournament: highest score2 in group
    for p in players:
        max_t2 = max(o.score2 for o in players if o != p)
        max_t2_all = max(o.score2 for o in players)
        p.won_tournament2 = (p.score2 >= max_t2_all) and (p.score2 > 0 or max_t2_all == 0)

    # Task-3 tournament: own score3 vs groupmates' SCORE2
    for p in players:
        others_score2 = [o.score2 for o in players if o != p]
        p.won_tournament3 = (p.choice3 == 'tour') and (p.score3 > max(others_score2))

    # Task-4 tournament: own score1 vs groupmates' SCORE1
    for p in players:
        others_score1 = [o.score1 for o in players if o != p]
        p.won_tournament4 = (p.choice4 == 'tour') and (p.score1 > max(others_score1))

    # Draw paid task and compute earnings
    for p in players:
        rng = random.Random(p.participant.code)
        p.paid_task = rng.randint(1, 4)
        p.task_earnings = _compute_task_earnings(p, players)
        p.belief_bonus = _belief_payoff(p, players)
        p.payoff = C.SHOWUP_FEE + C.COMPLETION_FEE + p.task_earnings + p.belief_bonus


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

class Welcome(Page):
    form_model = 'player'
    form_fields = ['gender', 'consent']

    @staticmethod
    def error_message(player, values):
        if not values.get('consent'):
            return 'You must consent to participate.'


class GroupingWaitPage(WaitPage):
    group_by_arrival_time = True
    title_text = 'Waiting for other participants'
    body_text = (
        'Please wait. We are forming groups of 2 men and 2 women. '
        'This may take a few minutes.'
    )


class Instructions1(Page):
    pass


def _live_task_handler(player, data):
    """
    Shared live_method handler for Task1, Task2, Task3.
    Called by the JS controller on each problem submission.
    """
    task = int(data['task'])
    idx = int(data['idx'])
    answer = int(data['answer'])
    response_ms = int(data['response_ms'])

    key = f'problems_{task}'
    problems = player.participant.vars[key]
    prob = problems[idx]
    correct_ans = sum(prob)
    is_correct = (answer == correct_ans)

    if is_correct:
        if task == 1:
            player.score1 += 1
        elif task == 2:
            player.score2 += 1
        elif task == 3:
            player.score3 += 1

    Attempt.create(
        player=player,
        task=task,
        problem_idx=idx,
        addends=json.dumps(prob),
        correct_answer=correct_ans,
        submitted=answer,
        is_correct=is_correct,
        response_ms=response_ms,
    )

    score = getattr(player, f'score{task}')
    next_idx = idx + 1
    next_prob = problems[next_idx] if next_idx < len(problems) else None

    return {player.id_in_group: dict(
        correct=is_correct,
        total=score,
        next_problem=next_prob,
        next_idx=next_idx,
    )}


class Task1(Page):
    timeout_seconds = C.TASK_SECONDS
    live_method = _live_task_handler

    @staticmethod
    def vars_for_template(player):
        problems = generate_problems(player.participant.code, 1)
        player.participant.vars['problems_1'] = problems
        player.participant.vars['seed_1'] = hash((player.participant.code, 1)) % (2 ** 32)
        return dict(
            first_problem=problems[0],
            task_num=1,
        )


class Results1(Page):
    @staticmethod
    def vars_for_template(player):
        return dict(score=player.score1)


class Instructions2(Page):
    pass


class Task2(Page):
    timeout_seconds = C.TASK_SECONDS
    live_method = _live_task_handler

    @staticmethod
    def vars_for_template(player):
        problems = generate_problems(player.participant.code, 2)
        player.participant.vars['problems_2'] = problems
        return dict(
            first_problem=problems[0],
            task_num=2,
        )


class Results2(Page):
    @staticmethod
    def vars_for_template(player):
        return dict(score=player.score2)


class Instructions3(Page):
    pass


class Choice3(Page):
    form_model = 'player'
    form_fields = ['choice3']


class Task3(Page):
    timeout_seconds = C.TASK_SECONDS
    live_method = _live_task_handler

    @staticmethod
    def vars_for_template(player):
        problems = generate_problems(player.participant.code, 3)
        player.participant.vars['problems_3'] = problems
        return dict(
            first_problem=problems[0],
            task_num=3,
        )


class Instructions4(Page):
    pass


class Choice4(Page):
    form_model = 'player'
    form_fields = ['choice4']


class Beliefs(Page):
    form_model = 'player'
    form_fields = ['belief_rank1', 'belief_rank2']


class ResultsWaitPage(WaitPage):
    after_all_players_arrive = set_payoffs
    title_text = 'Calculating results'
    body_text = 'Please wait while we calculate payoffs for all participants.'


class Results(Page):
    @staticmethod
    def vars_for_template(player):
        players = player.group.get_players()
        return dict(
            score1=player.score1,
            score2=player.score2,
            score3=player.score3,
            choice3=player.choice3,
            choice4=player.choice4,
            rank1=player.rank1,
            rank2=player.rank2,
            paid_task=player.paid_task,
            task_earnings=player.task_earnings,
            belief_bonus=player.belief_bonus,
            total_payoff=player.payoff,
            showup_fee=C.SHOWUP_FEE,
            completion_fee=C.COMPLETION_FEE,
        )


# ---------------------------------------------------------------------------
# Page sequence
# ---------------------------------------------------------------------------

page_sequence = [
    Welcome,
    GroupingWaitPage,
    Instructions1,
    Task1,
    Results1,
    Instructions2,
    Task2,
    Results2,
    Instructions3,
    Choice3,
    Task3,
    Instructions4,
    Choice4,
    Beliefs,
    ResultsWaitPage,
    Results,
]


# ---------------------------------------------------------------------------
# Custom export (long-format per Attempt, joined to player covariates)
# ---------------------------------------------------------------------------

def custom_export(players):
    yield [
        'participant_code', 'gender',
        'score1', 'score2', 'score3',
        'choice3', 'choice4',
        'belief_rank1', 'belief_rank2',
        'rank1', 'rank2',
        'paid_task', 'task_earnings', 'belief_bonus', 'payoff',
        'task', 'problem_idx', 'addends',
        'correct_answer', 'submitted', 'is_correct', 'response_ms',
    ]
    for p in players:
        for attempt in Attempt.filter(player=p):
            yield [
                p.participant.code,
                p.field_maybe_none('gender'),
                p.score1, p.score2, p.score3,
                p.field_maybe_none('choice3'),
                p.field_maybe_none('choice4'),
                p.field_maybe_none('belief_rank1'),
                p.field_maybe_none('belief_rank2'),
                p.field_maybe_none('rank1'),
                p.field_maybe_none('rank2'),
                p.field_maybe_none('paid_task'),
                p.field_maybe_none('task_earnings'),
                p.field_maybe_none('belief_bonus'),
                p.payoff,
                attempt.task, attempt.problem_idx, attempt.addends,
                attempt.correct_answer, attempt.submitted,
                attempt.is_correct, attempt.response_ms,
            ]
