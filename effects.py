"""Effect registry for TransCard (转牌).

Each effect is a standalone function registered via decorator.
To modify an effect, edit only its function — nothing else changes.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from constants import CardRank, load_config

if TYPE_CHECKING:
    from player import Player
    from card import Card


# ── registry ───────────────────────────────────────────────────────

EFFECT_REGISTRY = {}  # CardRank -> callable


def register_effect(rank):
    """Decorator to register an effect function for a card rank."""
    def decorator(fn):
        EFFECT_REGISTRY[rank] = fn
        return fn
    return decorator


def resolve_effects(triggers, ctx):
    """Execute effect triggers one by one, in order."""
    for rank, count in triggers:
        fn = EFFECT_REGISTRY.get(rank)
        if fn is None:
            continue
        for _ in range(count):
            fn(ctx)


class EffectContext:
    """Context passed to every effect function."""
    def __init__(self, game, source_player_idx):
        self.game = game
        self.source_player_idx = source_player_idx


# ── effect implementations ─────────────────────────────────────────


@register_effect(CardRank.ACE)
def effect_ace(ctx):
    """A — 指定一个玩家，你和他都摸 ace_draw 张牌."""
    cfg = load_config()
    n = cfg["effects"]["ace_draw"]
    game = ctx.game
    players = game.get_players()
    source = players[ctx.source_player_idx]

    target_idx = game.ask_choose_player(
        ctx.source_player_idx,
        "A效果：选择一位玩家，你和他各摸{}张牌".format(n),
    )
    target = players[target_idx]

    drawn = game.draw_cards(source, n)
    game.log("  A效果: {} 摸了 {} 张牌".format(source.name, len(drawn)))

    drawn2 = game.draw_cards(target, n)
    game.log("  A效果: {} 摸了 {} 张牌".format(target.name, len(drawn2)))


@register_effect(CardRank.JACK)
def effect_jack(ctx):
    """J — 指定一名玩家，让他的手牌数变为 jack_hand_target 张."""
    cfg = load_config()
    target_size = cfg["effects"]["jack_hand_target"]
    game = ctx.game
    players = game.get_players()

    target_idx = game.ask_choose_player(
        ctx.source_player_idx,
        "J效果：选择一位玩家，使其手牌数变为{}".format(target_size),
    )
    target = players[target_idx]
    current = target.hand_size()

    if current > target_size:
        excess = current - target_size
        to_discard = random.sample(target.hand, excess)
        game.discard_from_hand(target, to_discard)
        game.log("  J效果: {} 弃掉了 {} 张牌 (剩余{})".format(
            target.name, excess, target.hand_size()))
    elif current < target_size:
        need = target_size - current
        drawn = game.draw_cards(target, need)
        game.log("  J效果: {} 补了 {} 张牌 (共{})".format(
            target.name, len(drawn), target.hand_size()))
    else:
        game.log("  J效果: {} 手牌已经是{}张，无变化".format(target.name, target_size))


@register_effect(CardRank.QUEEN)
def effect_queen(ctx):
    """Q — 所有玩家选 queen_return 张牌洗回牌库。
    如果此操作使手牌为0，该玩家摸 queen_empty_draw 张牌."""
    cfg = load_config()
    n = cfg["effects"]["queen_return"]
    empty_draw = cfg["effects"]["queen_empty_draw"]
    game = ctx.game
    players = game.get_players()

    for p in players:
        if p.hand_size() == 0:
            continue
        actual_n = min(n, p.hand_size())
        chosen = game.ask_choose_cards(
            p.idx, actual_n,
            "Q效果：选择{}张牌洗回牌库".format(actual_n),
        )
        p.remove_from_hand(chosen)
        game.shuffle_into_deck(chosen)
        game.log("  Q效果: {} 将{}张牌洗回牌库".format(p.name, len(chosen)))

        if p.hand_size() == 0:
            drawn = game.draw_cards(p, empty_draw)
            game.log("  Q效果: {} 手牌为0，摸了{}张牌".format(p.name, len(drawn)))


@register_effect(CardRank.KING)
def effect_king(ctx):
    """K — 所有玩家依次摸 king_draw 张牌."""
    cfg = load_config()
    n = cfg["effects"]["king_draw"]
    game = ctx.game
    players = game.get_players()

    for p in players:
        drawn = game.draw_cards(p, n)
        game.log("  K效果: {} 摸了 {} 张牌".format(p.name, len(drawn)))


@register_effect(CardRank.JOKER_BLACK)
def effect_joker_black(ctx):
    """黑Joker — 指定2个玩家，混洗手牌平分。奇数时从牌库补1张."""
    game = ctx.game
    players = game.get_players()

    idx1 = game.ask_choose_player(
        ctx.source_player_idx,
        "黑Joker：选择第1位玩家",
    )
    idx2 = game.ask_choose_player(
        ctx.source_player_idx,
        "黑Joker：选择第2位玩家",
        exclude=[idx1],
    )
    p1, p2 = players[idx1], players[idx2]

    combined = list(p1.hand) + list(p2.hand)

    if len(combined) % 2 == 1:
        extra = game.draw_cards(p1, 1)
        if extra:
            combined.extend(extra)
            game.log("  黑Joker: 牌数为奇数，从牌库补1张")

    random.shuffle(combined)
    half = len(combined) // 2

    p1.hand.clear()
    p2.hand.clear()
    p1.add_to_hand(combined[:half])
    p2.add_to_hand(combined[half:])

    game.log("  黑Joker: {}({}张) 和 {}({}张) 的手牌已混洗平分".format(
        p1.name, p1.hand_size(), p2.name, p2.hand_size()))


@register_effect(CardRank.JOKER_RED)
def effect_joker_red(ctx):
    """红Joker — 选1位玩家，手牌洗入牌库，重抽等量的牌。
    若原手牌数 <= threshold，额外抽 bonus 张."""
    cfg = load_config()
    bonus = cfg["effects"]["joker_red_bonus_draw"]
    threshold = cfg["effects"]["joker_red_bonus_threshold"]
    game = ctx.game
    players = game.get_players()

    target_idx = game.ask_choose_player(
        ctx.source_player_idx,
        "红Joker：选择一位玩家，将其手牌洗入牌库后重抽",
    )
    target = players[target_idx]
    original_count = target.hand_size()

    cards_to_return = list(target.hand)
    target.hand.clear()
    game.shuffle_into_deck(cards_to_return)
    game.log("  红Joker: {} 的{}张手牌洗入牌库".format(target.name, original_count))

    draw_count = original_count
    if original_count <= threshold:
        draw_count += bonus
        game.log("  红Joker: 原手牌<={}张，额外抽{}张".format(threshold, bonus))

    drawn = game.draw_cards(target, draw_count)
    game.log("  红Joker: {} 重新抽了{}张牌".format(target.name, len(drawn)))
