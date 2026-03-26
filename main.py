#!/usr/bin/env python3
"""TransCard (转牌) — entry point."""

from __future__ import annotations

import argparse

from ai import AIBridge, RandomAI, GreedyAI, DefensiveAI
from game import Game
from ui import CLIBridge, set_game_ref

AI_TYPES = {
    "random": RandomAI,
    "greedy": GreedyAI,
    "defensive": DefensiveAI,
}


def main():
    parser = argparse.ArgumentParser(description="转牌 — TransCard")
    parser.add_argument("--players", type=int, default=4, help="总玩家数 (3-6)")
    parser.add_argument("--ai", type=int, default=0, help="AI玩家数量")
    parser.add_argument("--ai-type", default="greedy", choices=AI_TYPES.keys(),
                        help="AI策略类型")
    args = parser.parse_args()

    n = max(3, min(6, args.players))
    n_ai = max(0, min(n, args.ai))
    n_human = n - n_ai

    names = ["玩家{}".format(i+1) for i in range(n_human)] + \
            ["AI_{}_{}".format(args.ai_type, i+1) for i in range(n_ai)]
    human_flags = [True] * n_human + [False] * n_ai

    game = Game(bridge=None)

    if n_human > 0:
        bridge = CLIBridge()
        set_game_ref(game)
        game.bridge = bridge
    else:
        ai_cls = AI_TYPES[args.ai_type]
        strategies = {i: ai_cls() for i in range(n)}
        bridge = AIBridge(strategies, game)
        game.bridge = bridge

    game.setup(names, human_flags)
    game.run()


if __name__ == "__main__":
    main()
