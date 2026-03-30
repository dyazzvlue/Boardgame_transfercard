"""
TransCard/online/state.py
将游戏状态序列化为 JSON dict，供 get_state() 和 WebSocket STATE 广播。
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..player import Player
    from ..card import Card, Deck


def _card_to_dict(card):
    """Card -> JSON dict."""
    return {
        "uid": card.uid,
        "suit": card.suit.value if hasattr(card.suit, 'value') else str(card.suit),
        "rank": card.rank_value,
        "name": card.short_name(),
        "is_effect": card.is_effect,
        "is_joker": card.is_joker,
    }


def _player_to_dict(player, hide_hand=False):
    """Player -> JSON dict. hide_hand=True 时只发手牌数量不发具体牌。"""
    d = {
        "name": player.name,
        "idx": player.idx,
        "is_human": getattr(player, 'is_human', True),
        "hand_size": player.hand_size(),
        "total_score": player.total_score(),
        "scored": [
            {
                "type": ctype.value,
                "cards": [_card_to_dict(c) for c in cards],
                "score": score,
            }
            for ctype, cards, score in player.scored
        ],
    }
    if not hide_hand:
        d["hand"] = [_card_to_dict(c) for c in player.hand]
    return d


def serialize_state(game, viewer_idx=None):
    """
    将 Game 对象序列化为 JSON dict。
    viewer_idx: 当前观看者的玩家索引，只显示该玩家的手牌，其他人只显示手牌数量。
    如果 viewer_idx 为 None，显示所有人手牌（调试模式）。
    """
    players_data = []
    for p in game.players:
        hide = (viewer_idx is not None and p.idx != viewer_idx)
        players_data.append(_player_to_dict(p, hide_hand=hide))

    return {
        "phase": "playing" if not game.game_over else "finished",
        "turn": game.turn,
        "current_idx": game.current_idx,
        "game_over": game.game_over,
        "game_over_reason": game.game_over_reason,
        "deck_remaining": game.deck.remaining,
        "discard_count": game.discard.size,
        "players": players_data,
    }
