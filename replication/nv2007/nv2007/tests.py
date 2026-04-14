"""
Browser-bot tests for the nv2007 app.

Run: otree test nv2007 --num-participants=4

Bot design:
- Bot 1: Male,   high scorer  — picks tournament both times, guesses rank 1
- Bot 2: Male,   low scorer   — picks piece rate both times, guesses rank 4
- Bot 3: Female, high scorer  — picks tournament for T3, piece rate for T4, guesses rank 1
- Bot 4: Female, zero scorer  — submits wrong answers, picks piece rate, guesses rank 4

These cover: high/low performers, gender split (2M+2F), tournament vs piece rate,
tie-breaking (bots 1 & 3 may tie), incorrect submissions.
"""

from otree.api import Bot, Submission

from . import (
    Beliefs,
    Choice3,
    Choice4,
    GroupingWaitPage,
    Instructions1,
    Instructions2,
    Instructions3,
    Instructions4,
    Results,
    Results1,
    Results2,
    ResultsWaitPage,
    Task1,
    Task2,
    Task3,
    Welcome,
    generate_problems,
)


class PlayerBot(Bot):
    """
    Bots are assigned sequentially to players 1–4 within a group.
    We parameterise by player index (1-based) using cases.
    """

    def play_round(self):
        pid = self.player.id_in_group  # 1–4

        # --- Welcome ---
        if pid in (1, 2):
            gender = 'M'
        else:
            gender = 'F'
        yield Submission(Welcome, dict(gender=gender, consent=True), check_html=False)

        # --- Grouping wait ---
        yield Submission(GroupingWaitPage, check_html=False)

        # --- Task 1 ---
        yield Submission(Instructions1, check_html=False)
        n_correct_1 = {1: 15, 2: 5, 3: 14, 4: 0}[pid]
        yield self._play_task(Task1, self.participant.code, 1, n_correct_1)
        yield Submission(Results1, check_html=False)

        # --- Task 2 ---
        yield Submission(Instructions2, check_html=False)
        n_correct_2 = {1: 16, 2: 4, 3: 16, 4: 0}[pid]
        yield self._play_task(Task2, self.participant.code, 2, n_correct_2)
        yield Submission(Results2, check_html=False)

        # --- Task 3 (choice + perform) ---
        yield Submission(Instructions3, check_html=False)
        choice3 = {1: 'tour', 2: 'piece', 3: 'tour', 4: 'piece'}[pid]
        yield Submission(Choice3, dict(choice3=choice3), check_html=False)
        n_correct_3 = {1: 14, 2: 6, 3: 14, 4: 0}[pid]
        yield self._play_task(Task3, self.participant.code, 3, n_correct_3)

        # --- Task 4 (past performance choice) ---
        yield Submission(Instructions4, check_html=False)
        choice4 = {1: 'tour', 2: 'piece', 3: 'piece', 4: 'piece'}[pid]
        yield Submission(Choice4, dict(choice4=choice4), check_html=False)

        # --- Beliefs ---
        belief_rank1 = {1: 1, 2: 4, 3: 2, 4: 4}[pid]
        belief_rank2 = {1: 1, 2: 4, 3: 1, 4: 4}[pid]
        yield Submission(
            Beliefs,
            dict(belief_rank1=belief_rank1, belief_rank2=belief_rank2),
            check_html=False,
        )

        # --- Wait for payoffs ---
        yield Submission(ResultsWaitPage, check_html=False)

        # --- Results: basic sanity checks ---
        yield Submission(Results, check_html=False)

    def _play_task(self, page_class, participant_code, task_num, n_correct):
        """
        Simulate a task page by sending live messages for n_correct correct answers,
        then let the timeout expire (bots auto-submit timed pages).
        """
        problems = generate_problems(participant_code, task_num)
        calls = []
        for i in range(n_correct):
            calls.append(dict(
                task=task_num,
                idx=i,
                answer=sum(problems[i]),
                response_ms=1000,
            ))
        # Send one wrong answer after correct ones so scoring is testable
        if n_correct < len(problems):
            calls.append(dict(
                task=task_num,
                idx=n_correct,
                answer=sum(problems[n_correct]) + 99,  # definitely wrong
                response_ms=500,
            ))
        return Submission(page_class, live_method_calls=calls, check_html=False)
