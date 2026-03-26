"""TransCard (转牌) — enums and config loader."""

from __future__ import annotations

import json
import os
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any

# ── paths ──────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_CONFIG = _DATA_DIR / "config.json"


# ── enums ──────────────────────────────────────────────────────────
class Suit(Enum):
    SPADES = "spades"
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"


SUIT_ALL = [Suit.SPADES, Suit.HEARTS, Suit.DIAMONDS, Suit.CLUBS]

RED_SUITS = {Suit.HEARTS, Suit.DIAMONDS}
BLACK_SUITS = {Suit.SPADES, Suit.CLUBS}


class CardRank(IntEnum):
    ACE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    JOKER_BLACK = 14
    JOKER_RED = 15


EFFECT_RANKS = {CardRank.ACE, CardRank.JACK, CardRank.QUEEN, CardRank.KING}
JOKER_RANKS = {CardRank.JOKER_BLACK, CardRank.JOKER_RED}
NORMAL_RANKS = {r for r in CardRank if r not in EFFECT_RANKS and r not in JOKER_RANKS}


class CardType(Enum):
    NORMAL = "normal"
    EFFECT = "effect"
    JOKER = "joker"


def rank_type(rank: CardRank) -> CardType:
    if rank in JOKER_RANKS:
        return CardType.JOKER
    if rank in EFFECT_RANKS:
        return CardType.EFFECT
    return CardType.NORMAL


class ActionType(Enum):
    DRAW_DECK = "draw_deck"           # 行动1：从牌库抽牌
    DRAW_PLAYER = "draw_player"       # 行动2：从玩家手里盲抽
    RETURN_AND_DRAW = "return_draw"   # 行动3：放1张到牌库底，摸1张
    PLAY_CARDS = "play_cards"         # 行动4：打出牌型


class CombinationType(Enum):
    SAME = "same"                     # n张相同点数
    STRAIGHT = "straight"             # 顺子
    FLUSH_STRAIGHT = "flush_straight" # 同花顺
    SINGLE = "single"                 # 单打（仅效果牌/Joker）


# ── config ─────────────────────────────────────────────────────────
_config_cache = None


def load_config(path=None):
    """Load and cache the JSON config."""
    global _config_cache
    if _config_cache is not None and path is None:
        return _config_cache
    p = Path(path) if path else _DEFAULT_CONFIG
    with open(p, encoding="utf-8") as f:
        cfg = json.load(f)
    if path is None:
        _config_cache = cfg
    return cfg


def reset_config_cache():
    """Clear cached config (useful for tests with custom configs)."""
    global _config_cache
    _config_cache = None
