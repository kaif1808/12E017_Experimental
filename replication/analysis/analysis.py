"""
Pre-registered analysis for NV 2007 replication.

Usage:
    python analysis.py --data path/to/custom_export.csv

Outputs:
    - Fisher's exact test (Table I equivalent)
    - Probit regressions 1–3 (Task-3 entry)
    - Probit regression (Task-4 entry)
    - Decomposition table (cascade of female marginal effects)

Dependencies: pandas, scipy, statsmodels
    pip install pandas scipy statsmodels
"""

import argparse
import sys
import warnings

import pandas as pd
from scipy.stats import fisher_exact


def load_data(path: str) -> pd.DataFrame:
    """Load and deduplicate the custom export (wide: one row per player)."""
    raw = pd.read_csv(path)
    # The custom export is long (one row per Attempt); collapse to player level.
    # Keep only the first row per participant (all player-level fields are identical).
    wide = (
        raw.drop_duplicates(subset=['participant_code'])
        .copy()
        .reset_index(drop=True)
    )
    return wide


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['female'] = (df['gender'] == 'F').astype(int)
    df['entered_tour3'] = (df['choice3'] == 'tour').astype(int)
    df['entered_tour4'] = (df['choice4'] == 'tour').astype(int)
    df['score_diff'] = df['score2'] - df['score1']
    # Recode belief_rank2: higher value → more confident (1=most confident)
    # Recode so that larger number = more confident, as in NV2007
    df['confidence2'] = 5 - df['belief_rank2']   # rank 1 → 4, rank 4 → 1
    df['confidence1'] = 5 - df['belief_rank1']
    return df


def fisher_test(df: pd.DataFrame) -> None:
    """
    Primary test: Fisher's exact test on tournament entry (Task 3) by gender.
    H0: entry rate is the same for men and women.
    """
    print("=" * 60)
    print("Fisher's Exact Test: Task-3 Tournament Entry by Gender")
    print("=" * 60)

    ct = pd.crosstab(df['gender'], df['entered_tour3'])
    ct.columns = ['Piece Rate', 'Tournament']
    print(ct)

    m_tour = df.loc[df['gender'] == 'M', 'entered_tour3'].mean()
    f_tour = df.loc[df['gender'] == 'F', 'entered_tour3'].mean()
    print(f"\nMale entry rate:   {m_tour:.1%}")
    print(f"Female entry rate: {f_tour:.1%}")

    table = ct.values
    odds, p = fisher_exact(table, alternative='greater')
    print(f"\nFisher exact p-value (one-sided, male > female): {p:.4f}")
    print()


def run_probits(df: pd.DataFrame) -> None:
    """
    Probit regressions for Task-3 tournament entry (Table II equivalent).

    Model 1: choice3 ~ female + score2 + score_diff
    Model 2: + confidence2
    Model 3: + entered_tour4
    """
    try:
        import statsmodels.api as sm
        from statsmodels.discrete.discrete_model import Probit
    except ImportError:
        print("statsmodels not available; skipping probit regressions.")
        return

    print("=" * 60)
    print("Probit Regressions: Task-3 Tournament Entry")
    print("=" * 60)

    base_X = df[['female', 'score2', 'score_diff']].copy()
    base_X = sm.add_constant(base_X)
    y = df['entered_tour3']

    specs = [
        ('Model 1 (perf)', base_X),
        ('Model 2 (+ confidence)', sm.add_constant(
            df[['female', 'score2', 'score_diff', 'confidence2']])),
        ('Model 3 (+ tour4 choice)', sm.add_constant(
            df[['female', 'score2', 'score_diff', 'confidence2', 'entered_tour4']])),
    ]

    marginal_effects = []
    for name, X in specs:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            try:
                res = Probit(y, X).fit(disp=False)
                # Marginal effect of female at mean
                me = res.get_margeff()
                female_me = me.margeff[X.columns.tolist().index('female') - 1]
                female_pval = me.pvalues[X.columns.tolist().index('female') - 1]
                marginal_effects.append((name, female_me, female_pval))
                print(f"\n{name}")
                print(res.summary2().tables[1])
            except Exception as e:
                print(f"{name}: failed ({e})")

    print("\nDecomposition table — female marginal effect on Task-3 entry:")
    print(f"{'Model':<40} {'ME (pp)':>10} {'p-value':>10}")
    print("-" * 62)
    for name, me, pval in marginal_effects:
        print(f"{name:<40} {me * 100:>10.1f} {pval:>10.4f}")
    print()


def task4_probit(df: pd.DataFrame) -> None:
    """
    Probit for Task-4 tournament entry.
    Model: choice4 ~ female + score1 + confidence1
    """
    try:
        import statsmodels.api as sm
        from statsmodels.discrete.discrete_model import Probit
    except ImportError:
        return

    print("=" * 60)
    print("Probit Regression: Task-4 Tournament Entry")
    print("=" * 60)

    X = sm.add_constant(df[['female', 'score1', 'confidence1']])
    y = df['entered_tour4']

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        try:
            res = Probit(y, X).fit(disp=False)
            print(res.summary2().tables[1])
            me = res.get_margeff()
            female_me = me.margeff[X.columns.tolist().index('female') - 1]
            female_pval = me.pvalues[X.columns.tolist().index('female') - 1]
            print(f"\nFemale marginal effect: {female_me * 100:.1f} pp (p={female_pval:.4f})")
            print("Hypothesis: coefficient → 0 once controlling for performance + confidence\n")
        except Exception as e:
            print(f"Task-4 probit failed: {e}")


def descriptives(df: pd.DataFrame) -> None:
    print("=" * 60)
    print("Descriptive Statistics")
    print("=" * 60)
    cols = ['score1', 'score2', 'score3', 'entered_tour3', 'entered_tour4',
            'confidence1', 'confidence2']
    print(df.groupby('gender')[cols].mean().round(2).to_string())
    print()


def main():
    parser = argparse.ArgumentParser(description='NV2007 Replication Analysis')
    parser.add_argument('--data', required=True, help='Path to custom_export.csv')
    args = parser.parse_args()

    df = load_data(args.data)
    df = prepare(df)

    print(f"\nN = {len(df)} participants, "
          f"{(df.gender == 'M').sum()} male, "
          f"{(df.gender == 'F').sum()} female\n")

    descriptives(df)
    fisher_test(df)
    run_probits(df)
    task4_probit(df)


if __name__ == '__main__':
    main()
