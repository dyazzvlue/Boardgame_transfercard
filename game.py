"""Core game engine for TransCard (转牌)."""

from __future__ import annotations

import random

from card import Card, Deck, DiscardPile
from constants import (
    ActionType, CardRank, CombinationType, load_config,
)
from effects import EffectContext, resolve_effects
from player import Player
from rules import (
    classify_combination, calculate_score, get_effect_triggers,
)


class Game:
    """Main game engine. Interacts with players through a *bridge* object.

    Bridge must implement:
        ask_action(player_idx, available) -> ActionType
        ask_select_cards(player_idx, purpose, n=None) -> list[Card]
        ask_select_player(source_idx, prompt, exclude) -> int
        log(text)
        show_state(game)
    """

    def __init__(self, bridge):
        self.bridge = bridge
        self.players = []
        self.deck = Deck()
        self.discard = DiscardPile()
        self.turn = 0
        self.current_idx = 0
        self.game_over = False
        self.game_over_reason = ""
        self._no_play_rounds = 0
        self._anyone_played_this_round = False
        self._cfg = {}

    # ── setup ──────────────────────────────────────────────────

    def setup(self, player_names, human_flags):
        self._cfg = load_config()

        self.players = [
            Player(name, i, is_human=hf)
            for i, (name, hf) in enumerate(zip(player_names, human_flags))
        ]

        self.deck = Deck.standard(self._cfg["game"]["deck_count"])
        self.deck.shuffle()

        hand_size = self._cfg["game"]["hand_size"]
        for p in self.players:
            p.add_to_hand(self.deck.draw(hand_size))

    # ── main loop ──────────────────────────────────────────────

    def run(self):
        n = len(self.players)
        stalemate_limit = self._cfg["game"]["stalemate_rounds"]

        while not self.game_over:
            self._anyone_played_this_round = False

            for seat in range(n):
                if self.game_over:
                    break

                self.current_idx = seat
                player = self.players[self.current_idx]

                self.bridge.show_state(self)
                self.bridge.log("\n" + "=" * 40)
                self.bridge.log("第{}轮 — {}的回合".format(self.turn + 1, player.name))

                available = self._get_available_actions(player)
                if not available:
                    self.bridge.log("{} 无可用行动，跳过".format(player.name))
                    continue

                action = self.bridge.ask_action(player.idx, available)
                self._execute_action(player, action)

                if self._check_game_over():
                    break

            self.turn += 1

            if not self.game_over:
                if not self._anyone_played_this_round:
                    self._no_play_rounds += 1
                    if self._no_play_rounds >= stalemate_limit:
                        self.game_over = True
                        self.game_over_reason = "连续{}轮无人出牌，游戏结束".format(stalemate_limit)
                        self.bridge.log("\n" + self.game_over_reason)
                else:
                    self._no_play_rounds = 0

        self.bridge.show_state(self)
        self._show_results()

    # ── available actions ──────────────────────────────────────

    def _get_available_actions(self, player):
        actions = []

        if not self.deck.is_empty:
            actions.append(ActionType.DRAW_DECK)

        others_with_cards = [p for p in self.players
                             if p.idx != player.idx and p.hand_size() > 0]
        if others_with_cards:
            actions.append(ActionType.DRAW_PLAYER)

        if player.hand_size() > 0 and not self.deck.is_empty:
            actions.append(ActionType.RETURN_AND_DRAW)

        if player.hand_size() > 0:
            actions.append(ActionType.PLAY_CARDS)

        return actions

    # ── action execution ───────────────────────────────────────

    def _execute_action(self, player, action):
        if action == ActionType.DRAW_DECK:
            self._do_draw_deck(player)
        elif action == ActionType.DRAW_PLAYER:
            self._do_draw_player(player)
        elif action == ActionType.RETURN_AND_DRAW:
            self._do_return_and_draw(player)
        elif action == ActionType.PLAY_CARDS:
            self._do_play_cards(player)

    def _do_draw_deck(self, player):
        n = self._cfg["game"]["draw_count"]
        drawn = self.draw_cards(player, n)
        self.bridge.log("{} 从牌库抽了 {} 张牌".format(player.name, len(drawn)))

    def _do_draw_player(self, player):
        others = [p for p in self.players
                  if p.idx != player.idx and p.hand_size() > 0]
        if not others:
            self.bridge.log("{} 没有可以抽牌的对象".format(player.name))
            return

        target_idx = self.bridge.ask_select_player(
            player.idx,
            "选择一位玩家盲抽1张牌",
            exclude=[player.idx],
        )
        target = self.players[target_idx]

        if target.hand_size() == 0:
            self.bridge.log("{} 没有手牌".format(target.name))
            return

        stolen = random.choice(target.hand)
        target.remove_from_hand([stolen])
        player.add_to_hand([stolen])
        self.bridge.log("{} 从 {} 手里抽了1张牌".format(player.name, target.name))

    def _do_return_and_draw(self, player):
        chosen = self.bridge.ask_select_cards(
            player.idx,
            "选择1张牌放到牌库底",
            n=1,
        )
        if not chosen:
            return
        card = chosen[0]
        player.remove_from_hand([card])
        self.deck.push_bottom(card)
        n = self._cfg["game"].get("return_draw_count", 2)
        drawn = self.draw_cards(player, n)
        self.bridge.log("{} 放回1张牌到牌库底，摸了{}张牌".format(player.name, len(drawn)))

    def _do_play_cards(self, player):
        cards = self.bridge.ask_select_cards(
            player.idx,
            "选择要打出的牌",
        )
        if not cards:
            self.bridge.log("{} 放弃出牌".format(player.name))
            return

        ctype, valid = classify_combination(cards)
        if not valid or ctype is None:
            self.bridge.log("无效的牌型组合")
            return

        player.remove_from_hand(cards)

        score = calculate_score(ctype, cards)
        card_names = " ".join(c.short_name() for c in cards)

        if ctype == CombinationType.SINGLE and cards[0].is_effect:
            self.discard.add(cards[0])
            self.bridge.log("{} 单打效果牌 {} (不计分)".format(player.name, card_names))
        else:
            player.add_to_score_zone(ctype, cards, score)
            self.bridge.log("{} 打出 [{}] {} → {}分".format(
                player.name, ctype.value, card_names, score))

        self._anyone_played_this_round = True

        triggers = get_effect_triggers(ctype, cards)
        if triggers:
            ctx = EffectContext(game=self, source_player_idx=player.idx)
            resolve_effects(triggers, ctx)

        # draw after play
        play_draw = self._cfg["game"].get("play_draw_count", 1)
        if play_draw > 0 and not self.deck.is_empty:
            bonus = self.draw_cards(player, play_draw)
            if bonus:
                self.bridge.log("{} 出牌后摸了{}张牌".format(player.name, len(bonus)))

    # ── game over check ────────────────────────────────────────

    def _check_game_over(self):
        for p in self.players:
            if p.hand_size() == 0:
                self.game_over = True
                self.game_over_reason = "{} 手牌清空，游戏结束！".format(p.name)
                self.bridge.log("\n" + self.game_over_reason)
                return True
        return False

    def _show_results(self):
        self.bridge.log("\n" + "=" * 40)
        self.bridge.log("最终得分：")
        ranked = sorted(self.players, key=lambda p: p.total_score(), reverse=True)
        for i, p in enumerate(ranked):
            marker = " 👑" if i == 0 else ""
            combos = len(p.scored)
            self.bridge.log("  {}. {}: {}分 ({}个牌型, 剩余{}张手牌){}".format(
                i + 1, p.name, p.total_score(), combos, p.hand_size(), marker))

    # ── GameInterface for effects ──────────────────────────────

    def get_players(self):
        return self.players

    def get_current_player_idx(self):
        return self.current_idx

    def draw_cards(self, player, n):
        drawn = self.deck.draw(n)
        player.add_to_hand(drawn)
        return drawn

    def discard_from_hand(self, player, cards):
        player.remove_from_hand(cards)
        self.discard.add_many(cards)

    def shuffle_into_deck(self, cards):
        self.deck.shuffle_in(cards)

    def ask_choose_player(self, source_idx, prompt, exclude=None):
        return self.bridge.ask_select_player(source_idx, prompt, exclude=exclude)

    def ask_choose_cards(self, player_idx, n, prompt):
        return self.bridge.ask_select_cards(player_idx, prompt, n=n)

    def log(self, text):
        self.bridge.log(text)
