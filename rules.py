"""Combination validation, scoring, and effect-trigger calculation.

All functions are pure — no side effects, no game state mutation.
"""

from __future__ import annotations

from collections import defaultdict

from card import Card
from constants import (
    CardRank, CardType, CombinationType,
    EFFECT_RANKS, JOKER_RANKS, rank_type, load_config,
)


# ── combination classification ─────────────────────────────────────


def classify_combination(cards):
    """Return (CombinationType, is_valid).  None if unrecognisable."""
    if not cards:
        return None, False

    if len(cards) == 1:
        return CombinationType.SINGLE, _is_valid_single(cards[0])

    # try flush straight first (more specific)
    if len(cards) >= 5 and _is_flush_straight(cards):
        return CombinationType.FLUSH_STRAIGHT, True

    if _is_same(cards):
        return CombinationType.SAME, True

    if len(cards) >= 3 and _is_straight(cards):
        return CombinationType.STRAIGHT, True

    return None, False


# ── individual validators ──────────────────────────────────────────


def _is_valid_single(card):
    return card.is_effect or card.is_joker


def _is_same(cards):
    """n >= 2 cards of same rank (jokers: same-colour pairing)."""
    if len(cards) < 2:
        return False

    first = cards[0]

    # joker pairing — must all be the same joker rank
    if first.is_joker:
        return all(c.rank == first.rank for c in cards)

    # normal / effect — same rank, not joker
    if any(c.is_joker for c in cards):
        return False
    return all(c.rank == first.rank for c in cards)


def _sorted_rank_values(cards):
    return sorted(c.rank_value for c in cards)


def _is_straight(cards):
    """n >= 3 consecutive ranks.  A can be low (A23) or high (QKA). No wrap (KA2)."""
    if len(cards) < 3:
        return False
    if any(c.is_joker for c in cards):
        return False

    vals = _sorted_rank_values(cards)

    # normal check: consecutive
    if _consecutive(vals):
        return True

    # high-ace check: treat A(1) as 14
    if 1 in vals:
        high_vals = sorted(14 if v == 1 else v for v in vals)
        if _consecutive(high_vals):
            return True

    return False


def _consecutive(vals):
    for i in range(1, len(vals)):
        if vals[i] != vals[i - 1] + 1:
            return False
    return True


def _is_flush_straight(cards):
    """Same-suit straight with n >= 5."""
    if len(cards) < 5:
        return False
    if any(c.suit is None for c in cards):
        return False
    if len({c.suit for c in cards}) != 1:
        return False
    return _is_straight(cards)


# ── scoring ────────────────────────────────────────────────────────


def calculate_score(ctype, cards):
    cfg = load_config()["scores"]

    if ctype == CombinationType.SAME:
        return _score_same(cards, cfg)
    if ctype == CombinationType.STRAIGHT:
        return _score_straight(cards, cfg)
    if ctype == CombinationType.FLUSH_STRAIGHT:
        return cfg["flush_straight"]
    if ctype == CombinationType.SINGLE:
        return _score_single(cards[0], cfg)
    return 0


def _score_same(cards, cfg):
    first = cards[0]
    if first.is_joker:
        per = cfg["joker_red"] if first.rank == CardRank.JOKER_RED else cfg["joker_black"]
        return per * len(cards)
    n = str(len(cards))
    return cfg["same"].get(n, 0)


def _score_straight(cards, cfg):
    n = len(cards)
    if n < 3:
        return 0
    return cfg["straight_base"] + (n - 3) * cfg["straight_extra_per_card"]


def _score_single(card, cfg):
    if card.rank == CardRank.JOKER_RED:
        return cfg.get("joker_red_single", cfg["joker_red"])
    if card.rank == CardRank.JOKER_BLACK:
        return cfg.get("joker_black_single", cfg["joker_black"])
    return 0


# ── effect triggers ────────────────────────────────────────────────


def get_effect_triggers(ctype, cards):
    """Return list of (CardRank, trigger_count) for cards that trigger effects.

    Rules:
    - SAME (n >= 2):  effect/joker triggers max(1, n-1) times
    - STRAIGHT:       only head & tail effect cards, 1 time each
    - FLUSH_STRAIGHT: only head & tail effect cards, 2 times each (doubled)
    - SINGLE:         1 time
    """
    if ctype == CombinationType.SINGLE:
        card = cards[0]
        if card.is_effect or card.is_joker:
            return [(card.rank, 1)]
        return []

    if ctype == CombinationType.SAME:
        return _triggers_same(cards)

    if ctype == CombinationType.STRAIGHT:
        return _triggers_straight(cards, multiplier=1)

    if ctype == CombinationType.FLUSH_STRAIGHT:
        return _triggers_straight(cards, multiplier=2)

    return []


def _triggers_same(cards):
    rank = cards[0].rank
    if rank not in EFFECT_RANKS and rank not in JOKER_RANKS:
        return []
    n = len(cards)
    count = max(1, n - 1)
    return [(rank, count)]


def _triggers_straight(cards, multiplier):
    """Only head (smallest) and tail (largest) effect/joker cards trigger."""
    vals = [c.rank_value for c in cards]
    has_ace = 1 in vals

    if has_ace:
        low_vals = sorted(vals)
        high_vals = sorted(14 if v == 1 else v for v in vals)
        if _consecutive(high_vals) and not _consecutive(low_vals):
            ordered = sorted(cards, key=lambda c: 14 if c.rank_value == 1 else c.rank_value)
        else:
            ordered = sorted(cards, key=lambda c: c.rank_value)
    else:
        ordered = sorted(cards, key=lambda c: c.rank_value)

    triggers = []
    head, tail = ordered[0], ordered[-1]

    if head.is_effect or head.is_joker:
        triggers.append((head.rank, 1 * multiplier))
    if tail != head and (tail.is_effect or tail.is_joker):
        triggers.append((tail.rank, 1 * multiplier))

    return triggers


# ── convenience ────────────────────────────────────────────────────


def find_all_valid_combinations(hand):
    """Enumerate all valid combinations from a hand (for AI use).

    Returns list of (CombinationType, cards, score) sorted by score desc.
    """
    results = []

    # singles
    for card in hand:
        if card.can_single_play:
            results.append((CombinationType.SINGLE, [card],
                            calculate_score(CombinationType.SINGLE, [card])))

    # same-rank groups
    rank_groups = defaultdict(list)
    for card in hand:
        rank_groups[card.rank].append(card)

    for rank, group in rank_groups.items():
        for size in range(2, len(group) + 1):
            subset = group[:size]
            ctype, valid = classify_combination(subset)
            if valid and ctype == CombinationType.SAME:
                results.append((ctype, list(subset),
                                calculate_score(ctype, subset)))

    # straights
    non_joker = [c for c in hand if not c.is_joker]
    _find_straights(non_joker, results)

    results.sort(key=lambda x: x[2], reverse=True)
    return results


def _find_straights(cards, out):
    """Find straight / flush-straight combinations via rank grouping."""
    rank_groups = defaultdict(list)
    for c in cards:
        rank_groups[c.rank_value].append(c)

    rank_vals = sorted(rank_groups.keys())
    if not rank_vals:
        return

    orderings = [rank_vals]
    if 1 in rank_vals:
        high = sorted(14 if v == 1 else v for v in rank_vals)
        orderings.append(high)

    seen = set()

    for ordering in orderings:
        for start_i in range(len(ordering)):
            run = [ordering[start_i]]
            for j in range(start_i + 1, len(ordering)):
                if ordering[j] == run[-1] + 1:
                    run.append(ordering[j])
                else:
                    break
            if len(run) < 3:
                continue

            for length in range(3, len(run) + 1):
                sub_run = run[:length]
                key = frozenset(sub_run)
                if key in seen:
                    continue
                seen.add(key)

                actual_ranks = [v if v != 14 else 1 for v in sub_run]

                combo = []
                for rv in actual_ranks:
                    combo.append(rank_groups[rv][0])

                ctype, valid = classify_combination(combo)
                if valid:
                    out.append((ctype, list(combo),
                                calculate_score(ctype, combo)))

                if length >= 5:
                    suit_map = defaultdict(list)
                    for rv in actual_ranks:
                        for c in rank_groups[rv]:
                            if c.suit is not None:
                                suit_map[c.suit].append(c)

                    for suit, suited in suit_map.items():
                        suited_ranks = {c.rank_value for c in suited}
                        if all(rv in suited_ranks for rv in actual_ranks):
                            flush_combo = []
                            for rv in actual_ranks:
                                for c in suited:
                                    if c.rank_value == rv:
                                        flush_combo.append(c)
                                        break
                            fc, fv = classify_combination(flush_combo)
                            if fv and fc == CombinationType.FLUSH_STRAIGHT:
                                out.append((fc, list(flush_combo),
                                            calculate_score(fc, flush_combo)))
