"""Unit tests for effects.py."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock
from card import Card, Deck, reset_uid_counter
from constants import CardRank, Suit, reset_config_cache
from player import Player
from effects import (
    EffectContext, resolve_effects,
    effect_ace, effect_jack, effect_queen, effect_king,
    effect_joker_black, effect_joker_red,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_uid_counter()
    reset_config_cache()


def _make_game(n_players=3, hand_size=5):
    players = [Player("P{}".format(i), i) for i in range(n_players)]
    deck = Deck.standard(1)
    deck.shuffle()
    for p in players:
        p.add_to_hand(deck.draw(hand_size))

    game = MagicMock()
    game.get_players.return_value = players
    game.get_current_player_idx.return_value = 0
    game.log = MagicMock()

    def draw_cards(player, n):
        drawn = deck.draw(n)
        player.add_to_hand(drawn)
        return drawn
    game.draw_cards = draw_cards

    def discard_from_hand(player, cards):
        player.remove_from_hand(cards)
    game.discard_from_hand = discard_from_hand

    def shuffle_into_deck(cards):
        deck.shuffle_in(cards)
    game.shuffle_into_deck = shuffle_into_deck

    game._deck = deck
    game._players = players
    return game, players, deck


class TestEffectAce:
    def test_both_draw(self):
        game, players, deck = _make_game()
        game.ask_choose_player = MagicMock(return_value=1)
        ctx = EffectContext(game=game, source_player_idx=0)
        i0, i1 = players[0].hand_size(), players[1].hand_size()
        effect_ace(ctx)
        assert players[0].hand_size() == i0 + 1
        assert players[1].hand_size() == i1 + 1

    def test_choose_self(self):
        game, players, deck = _make_game()
        game.ask_choose_player = MagicMock(return_value=0)
        ctx = EffectContext(game=game, source_player_idx=0)
        i0 = players[0].hand_size()
        effect_ace(ctx)
        assert players[0].hand_size() == i0 + 2


class TestEffectJack:
    def test_reduce(self):
        game, players, _ = _make_game(hand_size=8)
        game.ask_choose_player = MagicMock(return_value=1)
        effect_jack(EffectContext(game=game, source_player_idx=0))
        assert players[1].hand_size() == 5

    def test_increase(self):
        game, players, _ = _make_game(hand_size=2)
        game.ask_choose_player = MagicMock(return_value=1)
        effect_jack(EffectContext(game=game, source_player_idx=0))
        assert players[1].hand_size() == 5

    def test_no_change(self):
        game, players, _ = _make_game(hand_size=5)
        game.ask_choose_player = MagicMock(return_value=1)
        effect_jack(EffectContext(game=game, source_player_idx=0))
        assert players[1].hand_size() == 5


class TestEffectQueen:
    def test_all_return_one(self):
        game, players, deck = _make_game(hand_size=5)
        game.ask_choose_cards = MagicMock(
            side_effect=lambda idx, n, prompt: players[idx].hand[:n]
        )
        ctx = EffectContext(game=game, source_player_idx=0)
        deck_before = deck.remaining
        effect_queen(ctx)
        for p in players:
            assert p.hand_size() == 4
        assert deck.remaining == deck_before + 3

    def test_hand_zero_draws(self):
        game, players, deck = _make_game(hand_size=1)
        game.ask_choose_cards = MagicMock(
            side_effect=lambda idx, n, prompt: players[idx].hand[:n]
        )
        effect_queen(EffectContext(game=game, source_player_idx=0))
        for p in players:
            assert p.hand_size() == 2


class TestEffectKing:
    def test_all_draw(self):
        game, players, _ = _make_game(hand_size=5)
        effect_king(EffectContext(game=game, source_player_idx=0))
        for p in players:
            assert p.hand_size() == 6


class TestEffectJokerBlack:
    def test_shuffle_split(self):
        game, players, _ = _make_game(hand_size=5)
        game.ask_choose_player = MagicMock(side_effect=[0, 1])
        total = players[0].hand_size() + players[1].hand_size()
        effect_joker_black(EffectContext(game=game, source_player_idx=2))
        new_total = players[0].hand_size() + players[1].hand_size()
        assert new_total == total or new_total == total + 1
        assert abs(players[0].hand_size() - players[1].hand_size()) <= 0


class TestEffectJokerRed:
    def test_reshuffle(self):
        game, players, deck = _make_game(hand_size=5)
        game.ask_choose_player = MagicMock(return_value=1)
        effect_joker_red(EffectContext(game=game, source_player_idx=0))
        assert players[1].hand_size() == 5

    def test_bonus(self):
        game, players, deck = _make_game(hand_size=2)
        game.ask_choose_player = MagicMock(return_value=1)
        effect_joker_red(EffectContext(game=game, source_player_idx=0))
        assert players[1].hand_size() == 4


class TestResolveEffects:
    def test_multiple_k(self):
        game, players, _ = _make_game(hand_size=5)
        resolve_effects([(CardRank.KING, 2)], EffectContext(game=game, source_player_idx=0))
        for p in players:
            assert p.hand_size() == 7

    def test_mixed(self):
        game, players, _ = _make_game(hand_size=5)
        game.ask_choose_player = MagicMock(return_value=1)
        resolve_effects([
            (CardRank.ACE, 1),
            (CardRank.KING, 1),
        ], EffectContext(game=game, source_player_idx=0))
        assert players[0].hand_size() == 7
        assert players[1].hand_size() == 7
        assert players[2].hand_size() == 6
