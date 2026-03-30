"""
TransCard/online/adapter.py
将 TransCard 的 Game / bridge 包装为 framework 的 AbstractGame。
"""
from __future__ import annotations
import sys, os, random
from typing import Any

try:
    from framework.core import AbstractGame, AbstractBridge
except ImportError as _e:
    raise ImportError(
        "联机模式需要 gameplatform 框架。\n"
        "请运行: pip install -e /path/to/gameplatform\n"
        "原始错误: {}".format(_e)
    )

# 确保 TransCard 包自身可被 import
_TC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TC_DIR not in sys.path:
    sys.path.insert(0, _TC_DIR)

from constants import ActionType, CombinationType, CardRank
from card import Card
from player import Player
from ai import RandomAI, GreedyAI, DefensiveAI, AIStrategy
from game import Game
from .state import serialize_state, _card_to_dict


# ── Bridge 适配器 ──────────────────────────────────────────────────


class _TransCardNetBridge:
    """
    实现 game.py 需要的 bridge 接口，
    将每个交互调用映射到 AbstractBridge.ask()。

    game.py bridge 接口:
        log(text)
        show_state(game)
        ask_action(player_idx, available) -> ActionType
        ask_select_cards(player_idx, purpose, n=None) -> list[Card]
        ask_select_player(source_idx, prompt, exclude) -> int
    """

    def __init__(self, abstract_bridge, adapter):
        self._b = abstract_bridge
        self._adapter = adapter
        self._ai_strategies = {}  # player_idx -> AIStrategy

    def log(self, text):
        self._b.log(text)

    def show_state(self, game):
        self._b.broadcast_state()

    def ask_action(self, player_idx, available):
        # AI 玩家
        ai = self._ai_strategies.get(player_idx)
        if ai is not None:
            game = self._adapter._game
            player = game.players[player_idx]
            return ai.choose_action(player, available, game)

        self._b.broadcast_state()
        game = self._adapter._game
        player = game.players[player_idx]
        val = self._b.ask(player_idx, "choose_action", {
            "available": [a.value for a in available],
            "hand": [_card_to_dict(c) for c in player.hand],
        })
        if val is None:
            return available[0]
        try:
            return ActionType(val)
        except (ValueError, KeyError):
            return available[0]

    def ask_select_cards(self, player_idx, purpose, n=None):
        ai = self._ai_strategies.get(player_idx)
        if ai is not None:
            game = self._adapter._game
            player = game.players[player_idx]
            if n is not None:
                return ai.choose_cards_to_return(player, n, game)
            return ai.choose_cards_to_play(player, game)

        game = self._adapter._game
        player = game.players[player_idx]

        self._b.broadcast_state()
        val = self._b.ask(player_idx, "select_cards", {
            "purpose": purpose,
            "n": n,
            "hand": [_card_to_dict(c) for c in player.hand],
        })
        if val is None or not isinstance(val, list):
            return []

        # val 是 uid 列表，映射回 Card 对象
        uid_set = set(val)
        return [c for c in player.hand if c.uid in uid_set]

    def ask_select_player(self, source_idx, prompt, exclude=None):
        ai = self._ai_strategies.get(source_idx)
        if ai is not None:
            game = self._adapter._game
            return ai.choose_target_player(
                source_idx, game.players, exclude or [], game
            )

        game = self._adapter._game
        candidates = [
            {"idx": p.idx, "name": p.name, "hand_size": p.hand_size()}
            for p in game.players
            if p.idx not in (exclude or [])
        ]

        player = game.players[source_idx]
        self._b.broadcast_state()
        val = self._b.ask(source_idx, "select_player", {
            "prompt": prompt,
            "candidates": candidates,
            "hand": [_card_to_dict(c) for c in player.hand],
        })
        if val is None:
            return candidates[0]["idx"] if candidates else 0
        try:
            idx = int(val)
            if any(c["idx"] == idx for c in candidates):
                return idx
        except (ValueError, TypeError):
            pass
        return candidates[0]["idx"] if candidates else 0

    def set_ai(self, player_idx):
        self._ai_strategies[player_idx] = RandomAI()


# ── 主适配器 ──────────────────────────────────────────────────────


class TransCardGame(AbstractGame):
    GAME_ID     = "transcard"
    GAME_NAME   = "转牌"
    MIN_PLAYERS = 3
    MAX_PLAYERS = 6
    COVER_IMAGE = ""

    def __init__(self):
        self._game = None
        self._bridge_shim = None
        self._player_names = []
        self._human_flags = []

    def setup(self, player_names, human_flags):
        self._player_names = list(player_names)
        self._human_flags = list(human_flags)

        self._bridge_shim = _TransCardNetBridge(self.bridge, self)

        # 为 AI 玩家设置策略
        for i, is_human in enumerate(human_flags):
            if not is_human:
                self._bridge_shim.set_ai(i)

        self._game = Game(self._bridge_shim)
        self._game.setup(player_names, human_flags)

    def run(self):
        seed = random.randint(0, 2**31 - 1)
        random.seed(seed)
        self._game.run()

        # 游戏结束，广播最终结果
        ranked = sorted(self._game.players,
                        key=lambda p: p.total_score(), reverse=True)
        result = {
            "rankings": [
                {
                    "rank": i + 1,
                    "name": p.name,
                    "score": p.total_score(),
                    "combos": len(p.scored),
                    "hand_remaining": p.hand_size(),
                }
                for i, p in enumerate(ranked)
            ],
            "reason": self._game.game_over_reason,
        }
        self.bridge.broadcast_game_over(result)

    def get_state(self):
        if self._game is None:
            return {}
        # broadcast_state 发给所有人，隐藏所有手牌(仅显示手牌数量)
        # 玩家自己的手牌通过 ask_select_cards 请求中附带
        return serialize_state(self._game, viewer_idx=-1)

    def on_player_disconnected(self, player_idx):
        if self._bridge_shim is not None:
            self._bridge_shim.set_ai(player_idx)
            self.bridge.log("{}  断线，由 AI 接管".format(
                self._player_names[player_idx]))
