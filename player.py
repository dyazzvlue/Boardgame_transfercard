"""Player state for TransCard (转牌)."""

from __future__ import annotations

from card import Card
from constants import CombinationType


class Player:
    def __init__(self, name, idx, is_human=True):
        self.name = name
        self.idx = idx
        self.is_human = is_human
        self.hand = []
        self.scored = []  # list of (CombinationType, list[Card], int)

    def add_to_hand(self, cards):
        self.hand.extend(cards)

    def remove_from_hand(self, cards):
        uid_set = {c.uid for c in cards}
        self.hand = [c for c in self.hand if c.uid not in uid_set]

    def hand_size(self):
        return len(self.hand)

    def add_to_score_zone(self, ctype, cards, score):
        self.scored.append((ctype, list(cards), score))

    def total_score(self):
        return sum(s for _, _, s in self.scored)

    def hand_str(self):
        return " ".join(c.short_name() for c in self.hand)

    def __repr__(self):
        return "Player({}, hand={}, score={})".format(
            self.name, self.hand_size(), self.total_score())
