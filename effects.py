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
        exclude=[ctx.source_player_idx],
    )
    target = players[target_idx]

    drawn = game.draw_cards(source, n)
    game.log("  A效果: {} 摸了 {} 张牌".format(source.name, len(drawn)))

    drawn2 = game.draw_cards(target, n)
    game.log("  A效果: {} 摸了 {} 张牌".format(target.name, len(drawn2)))


# ── J 旧效果备份 ──
# def effect_jack_old(ctx):
#     """J(旧) — 指定一名玩家，让他的手牌数变为 jack_hand_target 张."""
#     cfg = load_config()
#     target_size = cfg["effects"]["jack_hand_target"]
#     game = ctx.game
#     players = game.get_players()
#     target_idx = game.ask_choose_player(
#         ctx.source_player_idx,
#         "J效果：选择一位玩家，使其手牌数变为{}".format(target_size),
#     )
#     target = players[target_idx]
#     current = target.hand_size()
#     if current > target_size:
#         excess = current - target_size
#         to_discard = random.sample(target.hand, excess)
#         game.discard_from_hand(target, to_discard)
#     elif current < target_size:
#         need = target_size - current
#         game.draw_cards(target, need)


@register_effect(CardRank.JACK)
def effect_jack(ctx):
    """J — 选择2名玩家，从他们手里各获得1张牌，
    然后可以保留其中0-1张，其余放到牌库底部."""
    cfg = load_config()
    jack_steal = cfg["effects"].get("jack_steal_count", 1)
    jack_keep = cfg["effects"].get("jack_keep_max", 1)
    game = ctx.game
    players = game.get_players()
    source = players[ctx.source_player_idx]

    # 选择2名有手牌的玩家
    others_with_cards = [p for p in players
                         if p.idx != ctx.source_player_idx and p.hand_size() > 0]
    if not others_with_cards:
        game.log("  J效果: 没有可以抽牌的目标")
        return

    stolen_cards = []

    # 第1个目标
    idx1 = game.ask_choose_player(
        ctx.source_player_idx,
        "J效果：选择第1位玩家抽取{}张牌".format(jack_steal),
        exclude=[ctx.source_player_idx],
    )
    target1 = players[idx1]
    if target1.hand_size() > 0:
        take1 = random.sample(target1.hand, min(jack_steal, target1.hand_size()))
        target1.remove_from_hand(take1)
        stolen_cards.extend(take1)
        game.log("  J效果: 从 {} 手里抽了{}张牌".format(target1.name, len(take1)))

    # 第2个目标（需要有别的玩家有牌）
    others2 = [p for p in players
               if p.idx != ctx.source_player_idx and p.idx != idx1 and p.hand_size() > 0]
    if others2:
        idx2 = game.ask_choose_player(
            ctx.source_player_idx,
            "J效果：选择第2位玩家抽取{}张牌".format(jack_steal),
            exclude=[ctx.source_player_idx, idx1],
        )
        target2 = players[idx2]
        if target2.hand_size() > 0:
            take2 = random.sample(target2.hand, min(jack_steal, target2.hand_size()))
            target2.remove_from_hand(take2)
            stolen_cards.extend(take2)
            game.log("  J效果: 从 {} 手里抽了{}张牌".format(target2.name, len(take2)))
    else:
        game.log("  J效果: 没有第2位可选目标")

    if not stolen_cards:
        return

    # 先全部加入手牌，再选择保留0~jack_keep张，其余放回牌库底
    source.add_to_hand(stolen_cards)

    if len(stolen_cards) <= jack_keep:
        # 全部保留
        game.log("  J效果: {} 保留了全部{}张牌".format(source.name, len(stolen_cards)))
    else:
        # 选择要放回的牌
        return_count = len(stolen_cards) - jack_keep
        to_return = game.ask_choose_cards(
            ctx.source_player_idx, return_count,
            "J效果：选择{}张牌放到牌库底部（保留{}张）".format(return_count, jack_keep),
        )
        source.remove_from_hand(to_return)
        for card in to_return:
            game.deck.push_bottom(card)
        game.log("  J效果: {} 保留了{}张，放回{}张到牌库底".format(
            source.name, jack_keep, len(to_return)))


@register_effect(CardRank.QUEEN)
def effect_queen(ctx):
    """Q — 其余玩家选 queen_return 张牌洗回牌库。
    如果此操作使手牌为0，该玩家摸 queen_empty_draw 张牌."""
    cfg = load_config()
    n = cfg["effects"]["queen_return"]
    empty_draw = cfg["effects"]["queen_empty_draw"]
    game = ctx.game
    players = game.get_players()

    for p in players:
        if p.idx == ctx.source_player_idx:
            continue
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
