"""Unit tests for rules.py."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from card import Card, reset_uid_counter
from constants import CardRank, Suit, CombinationType, reset_config_cache
from rules import (
    classify_combination, calculate_score, get_effect_triggers,
    _is_same, _is_straight, _is_flush_straight,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_uid_counter()
    reset_config_cache()


def C(rank_val, suit=Suit.SPADES):
    return Card(CardRank(rank_val), suit)

def joker_b():
    return Card(CardRank.JOKER_BLACK)

def joker_r():
    return Card(CardRank.JOKER_RED)


class TestSame:
    def test_pair(self):
        assert _is_same([C(5, Suit.SPADES), C(5, Suit.HEARTS)])

    def test_triple(self):
        assert _is_same([C(10), C(10, Suit.HEARTS), C(10, Suit.CLUBS)])

    def test_different_ranks(self):
        assert not _is_same([C(3), C(4)])

    def test_joker_same_color_pair(self):
        assert _is_same([joker_r(), joker_r()])

    def test_joker_mixed_not_same(self):
        assert not _is_same([joker_r(), joker_b()])

    def test_classify_same(self):
        ctype, valid = classify_combination([C(7), C(7, Suit.HEARTS), C(7, Suit.CLUBS)])
        assert ctype == CombinationType.SAME and valid


class TestStraight:
    def test_simple_345(self):
        assert _is_straight([C(3), C(4, Suit.HEARTS), C(5, Suit.DIAMONDS)])

    def test_a23_low(self):
        assert _is_straight([C(1), C(2, Suit.HEARTS), C(3, Suit.CLUBS)])

    def test_qka_high(self):
        assert _is_straight([C(12, Suit.HEARTS), C(13, Suit.CLUBS), C(1, Suit.SPADES)])

    def test_ka2_wrap_invalid(self):
        assert not _is_straight([C(13), C(1, Suit.HEARTS), C(2, Suit.CLUBS)])

    def test_10jqk(self):
        assert _is_straight([C(10), C(11, Suit.HEARTS), C(12, Suit.CLUBS), C(13, Suit.DIAMONDS)])

    def test_too_short(self):
        assert not _is_straight([C(3), C(4)])

    def test_non_consecutive(self):
        assert not _is_straight([C(3), C(5), C(7)])

    def test_jokers_not_in_straight(self):
        assert not _is_straight([C(3), C(4, Suit.HEARTS), joker_r()])

    def test_classify_straight(self):
        ctype, valid = classify_combination([C(5, Suit.SPADES), C(6, Suit.HEARTS), C(7, Suit.CLUBS)])
        assert ctype == CombinationType.STRAIGHT and valid

    def test_long_straight(self):
        assert _is_straight([C(3), C(4, Suit.HEARTS), C(5, Suit.CLUBS), C(6, Suit.DIAMONDS), C(7, Suit.SPADES)])


class TestFlushStraight:
    def test_five_card(self):
        cards = [C(5, Suit.HEARTS), C(6, Suit.HEARTS), C(7, Suit.HEARTS),
                 C(8, Suit.HEARTS), C(9, Suit.HEARTS)]
        assert _is_flush_straight(cards)

    def test_four_too_short(self):
        cards = [C(5, Suit.HEARTS), C(6, Suit.HEARTS), C(7, Suit.HEARTS), C(8, Suit.HEARTS)]
        assert not _is_flush_straight(cards)

    def test_different_suits(self):
        cards = [C(5, Suit.HEARTS), C(6, Suit.SPADES), C(7, Suit.HEARTS),
                 C(8, Suit.HEARTS), C(9, Suit.HEARTS)]
        assert not _is_flush_straight(cards)

    def test_classify_flush_straight(self):
        cards = [C(5, Suit.CLUBS), C(6, Suit.CLUBS), C(7, Suit.CLUBS),
                 C(8, Suit.CLUBS), C(9, Suit.CLUBS)]
        ctype, valid = classify_combination(cards)
        assert ctype == CombinationType.FLUSH_STRAIGHT and valid

    def test_with_ace_high(self):
        cards = [C(10, Suit.HEARTS), C(11, Suit.HEARTS), C(12, Suit.HEARTS),
                 C(13, Suit.HEARTS), C(1, Suit.HEARTS)]
        assert _is_flush_straight(cards)


class TestSingle:
    def test_effect_card(self):
        ctype, valid = classify_combination([C(1)])
        assert ctype == CombinationType.SINGLE and valid

    def test_joker(self):
        ctype, valid = classify_combination([joker_r()])
        assert ctype == CombinationType.SINGLE and valid

    def test_normal_invalid(self):
        ctype, valid = classify_combination([C(5)])
        assert ctype == CombinationType.SINGLE and not valid


class TestScoring:
    def test_pair_score(self):
        assert calculate_score(CombinationType.SAME, [C(5), C(5, Suit.HEARTS)]) == 2

    def test_triple_score(self):
        assert calculate_score(CombinationType.SAME, [C(5), C(5, Suit.HEARTS), C(5, Suit.CLUBS)]) == 2

    def test_quad_score(self):
        assert calculate_score(CombinationType.SAME, [C(5)] * 4) == 4

    def test_straight_3(self):
        assert calculate_score(CombinationType.STRAIGHT, [C(3), C(4), C(5)]) == 2

    def test_straight_5(self):
        assert calculate_score(CombinationType.STRAIGHT, [C(3), C(4), C(5), C(6), C(7)]) == 4

    def test_flush_straight_score(self):
        assert calculate_score(CombinationType.FLUSH_STRAIGHT, [C(5, Suit.HEARTS)] * 5) == 10

    def test_joker_red_single(self):
        assert calculate_score(CombinationType.SINGLE, [joker_r()]) == 3

    def test_joker_black_single(self):
        assert calculate_score(CombinationType.SINGLE, [joker_b()]) == 2

    def test_effect_single_no_score(self):
        assert calculate_score(CombinationType.SINGLE, [C(1)]) == 0

    def test_joker_red_pair(self):
        assert calculate_score(CombinationType.SAME, [joker_r(), joker_r()]) == 10

    def test_joker_black_pair(self):
        assert calculate_score(CombinationType.SAME, [joker_b(), joker_b()]) == 6


class TestEffectTriggers:
    def test_same_2_effect(self):
        triggers = get_effect_triggers(CombinationType.SAME, [C(1), C(1, Suit.HEARTS)])
        assert triggers == [(CardRank.ACE, 1)]

    def test_same_3_effect(self):
        triggers = get_effect_triggers(CombinationType.SAME, [C(11), C(11, Suit.HEARTS), C(11, Suit.CLUBS)])
        assert triggers == [(CardRank.JACK, 2)]

    def test_same_normal_no_triggers(self):
        assert get_effect_triggers(CombinationType.SAME, [C(5), C(5, Suit.HEARTS)]) == []

    def test_straight_tail_only(self):
        # 10, J, Q — tail=Q(effect)
        triggers = get_effect_triggers(CombinationType.STRAIGHT, [C(10), C(11, Suit.HEARTS), C(12, Suit.CLUBS)])
        assert triggers == [(CardRank.QUEEN, 1)]

    def test_straight_head_effect(self):
        # A, 2, 3 — head=A(effect)
        triggers = get_effect_triggers(CombinationType.STRAIGHT, [C(1), C(2, Suit.HEARTS), C(3, Suit.CLUBS)])
        assert triggers == [(CardRank.ACE, 1)]

    def test_straight_qka_both_ends(self):
        triggers = get_effect_triggers(CombinationType.STRAIGHT,
                                       [C(12, Suit.HEARTS), C(13, Suit.CLUBS), C(1, Suit.SPADES)])
        ranks = {r for r, _ in triggers}
        assert CardRank.QUEEN in ranks and CardRank.ACE in ranks

    def test_flush_straight_doubled(self):
        # 9,10,J,Q,K — tail=K(effect), doubled
        cards = [C(9, Suit.HEARTS), C(10, Suit.HEARTS), C(11, Suit.HEARTS),
                 C(12, Suit.HEARTS), C(13, Suit.HEARTS)]
        triggers = get_effect_triggers(CombinationType.FLUSH_STRAIGHT, cards)
        assert triggers == [(CardRank.KING, 2)]

    def test_single_effect(self):
        assert get_effect_triggers(CombinationType.SINGLE, [C(12)]) == [(CardRank.QUEEN, 1)]

    def test_single_joker(self):
        assert get_effect_triggers(CombinationType.SINGLE, [joker_r()]) == [(CardRank.JOKER_RED, 1)]

    def test_same_6_kings(self):
        cards = [C(13, s) for s in [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS, Suit.SPADES, Suit.HEARTS]]
        assert get_effect_triggers(CombinationType.SAME, cards) == [(CardRank.KING, 5)]
