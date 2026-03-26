"""AI strategies for TransCard (转牌)."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import Counter

from constants import ActionType, CombinationType
from rules import find_all_valid_combinations


class AIStrategy(ABC):
    @abstractmethod
    def choose_action(self, player, available, game):
        ...

    @abstractmethod
    def choose_cards_to_play(self, player, game):
        ...

    @abstractmethod
    def choose_cards_to_return(self, player, n, game):
        ...

    @abstractmethod
    def choose_target_player(self, source_idx, players, exclude, game):
        ...


class RandomAI(AIStrategy):
    def choose_action(self, player, available, game):
        return random.choice(available)

    def choose_cards_to_play(self, player, game):
        combos = find_all_valid_combinations(player.hand)
        if not combos:
            return []
        _, cards, _ = random.choice(combos)
        return cards

    def choose_cards_to_return(self, player, n, game):
        return random.sample(player.hand, min(n, len(player.hand)))

    def choose_target_player(self, source_idx, players, exclude, game):
        candidates = [p for p in players if p.idx not in exclude]
        return random.choice(candidates).idx


class GreedyAI(AIStrategy):
    def choose_action(self, player, available, game):
        if ActionType.PLAY_CARDS in available:
            combos = find_all_valid_combinations(player.hand)
            if combos and combos[0][2] >= 2:
                return ActionType.PLAY_CARDS
        if ActionType.DRAW_DECK in available:
            return ActionType.DRAW_DECK
        if ActionType.DRAW_PLAYER in available:
            return ActionType.DRAW_PLAYER
        if ActionType.RETURN_AND_DRAW in available:
            return ActionType.RETURN_AND_DRAW
        return random.choice(available)

    def choose_cards_to_play(self, player, game):
        combos = find_all_valid_combinations(player.hand)
        if not combos:
            return []
        return combos[0][1]

    def choose_cards_to_return(self, player, n, game):
        by_value = sorted(player.hand, key=lambda c: c.rank_value)
        return by_value[:min(n, len(by_value))]

    def choose_target_player(self, source_idx, players, exclude, game):
        candidates = [p for p in players if p.idx not in exclude]
        return max(candidates, key=lambda p: p.hand_size()).idx


class DefensiveAI(AIStrategy):
    def choose_action(self, player, available, game):
        if ActionType.PLAY_CARDS in available:
            combos = find_all_valid_combinations(player.hand)
            if combos:
                return ActionType.PLAY_CARDS
        if ActionType.RETURN_AND_DRAW in available:
            return ActionType.RETURN_AND_DRAW
        if ActionType.DRAW_PLAYER in available:
            return ActionType.DRAW_PLAYER
        return random.choice(available)

    def choose_cards_to_play(self, player, game):
        combos = find_all_valid_combinations(player.hand)
        if not combos:
            return []
        combos.sort(key=lambda x: len(x[1]), reverse=True)
        return combos[0][1]

    def choose_cards_to_return(self, player, n, game):
        rank_count = Counter(c.rank for c in player.hand)
        lonely = [c for c in player.hand if rank_count[c.rank] == 1]
        if lonely:
            return lonely[:min(n, len(lonely))]
        by_value = sorted(player.hand, key=lambda c: c.rank_value)
        return by_value[:min(n, len(by_value))]

    def choose_target_player(self, source_idx, players, exclude, game):
        candidates = [p for p in players if p.idx not in exclude]
        return min(candidates, key=lambda p: p.hand_size()).idx


class AIBridge:
    """Bridge that delegates decisions to AI strategies."""

    def __init__(self, strategies, game_ref, silent=False):
        self._strategies = strategies
        self._game = game_ref
        self._silent = silent
        self._logs = []

    def log(self, text):
        self._logs.append(text)
        if not self._silent:
            print(text)

    def show_state(self, game):
        pass

    def ask_action(self, player_idx, available):
        ai = self._strategies[player_idx]
        player = self._game.players[player_idx]
        return ai.choose_action(player, available, self._game)

    def ask_select_cards(self, player_idx, purpose, n=None):
        ai = self._strategies[player_idx]
        player = self._game.players[player_idx]
        if n is not None:
            return ai.choose_cards_to_return(player, n, self._game)
        return ai.choose_cards_to_play(player, self._game)

    def ask_select_player(self, source_idx, prompt, exclude=None):
        ai = self._strategies[source_idx]
        exclude = exclude or []
        return ai.choose_target_player(
            source_idx, self._game.players, exclude, self._game
        )
