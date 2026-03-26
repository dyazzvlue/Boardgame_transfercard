"""Card, Deck, and DiscardPile for TransCard (转牌)."""

from __future__ import annotations

import itertools
import random
from collections import deque

from constants import (
    CardRank, CardType, Suit, SUIT_ALL,
    EFFECT_RANKS, JOKER_RANKS, rank_type, load_config,
)

_uid_counter = itertools.count(1)


def _next_uid():
    return next(_uid_counter)


def reset_uid_counter():
    """Reset for deterministic tests."""
    global _uid_counter
    _uid_counter = itertools.count(1)


class Card:
    """A single playing card with a globally unique id."""

    __slots__ = ("suit", "rank", "uid")

    def __init__(self, rank, suit=None, uid=None):
        self.rank = rank
        self.suit = suit  # None for Jokers
        self.uid = uid if uid is not None else _next_uid()

    @property
    def card_type(self):
        return rank_type(self.rank)

    @property
    def is_effect(self):
        return self.rank in EFFECT_RANKS

    @property
    def is_joker(self):
        return self.rank in JOKER_RANKS

    @property
    def is_normal(self):
        return self.card_type == CardType.NORMAL

    @property
    def can_single_play(self):
        return self.is_effect or self.is_joker

    @property
    def rank_value(self):
        return int(self.rank)

    _SUIT_ICONS = {
        Suit.SPADES: "♠", Suit.HEARTS: "♥",
        Suit.DIAMONDS: "♦", Suit.CLUBS: "♣",
    }
    _RANK_NAMES = {
        1: "A", 11: "J", 12: "Q", 13: "K",
        14: "JokerB", 15: "JokerR",
    }

    def short_name(self):
        rn = self._RANK_NAMES.get(self.rank, str(int(self.rank)))
        if self.suit is None:
            return rn
        return "{}{}".format(self._SUIT_ICONS[self.suit], rn)

    def __repr__(self):
        return "Card({}, uid={})".format(self.short_name(), self.uid)

    def __eq__(self, other):
        if not isinstance(other, Card):
            return NotImplemented
        return self.uid == other.uid

    def __hash__(self):
        return hash(self.uid)


class Deck:
    """Draw pile backed by a deque (top = left)."""

    def __init__(self):
        self._cards = deque()

    @classmethod
    def standard(cls, deck_count=None):
        cfg = load_config()
        n = deck_count if deck_count is not None else cfg["game"]["deck_count"]
        d = cls()
        for _ in range(n):
            for suit in SUIT_ALL:
                for rank_val in range(1, 14):
                    d._cards.append(Card(CardRank(rank_val), suit))
            d._cards.append(Card(CardRank.JOKER_BLACK))
            d._cards.append(Card(CardRank.JOKER_RED))
        return d

    def shuffle(self):
        lst = list(self._cards)
        random.shuffle(lst)
        self._cards = deque(lst)

    def draw(self, n=1):
        result = []
        for _ in range(n):
            if not self._cards:
                break
            result.append(self._cards.popleft())
        return result

    def push_bottom(self, card):
        self._cards.append(card)

    def shuffle_in(self, cards):
        for card in cards:
            if self._cards:
                pos = random.randint(0, len(self._cards))
                self._cards.insert(pos, card)
            else:
                self._cards.append(card)

    @property
    def remaining(self):
        return len(self._cards)

    @property
    def is_empty(self):
        return len(self._cards) == 0

    def __len__(self):
        return len(self._cards)


class DiscardPile:
    def __init__(self):
        self.cards = []

    def add(self, card):
        self.cards.append(card)

    def add_many(self, cards):
        self.cards.extend(cards)

    @property
    def size(self):
        return len(self.cards)
