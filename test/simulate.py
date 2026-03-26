#!/usr/bin/env python3
"""Automated balance simulation for TransCard (转牌).

Usage:
    python simulate.py --games 1000 --players 4 --ai random
    python simulate.py --games 500 --players 4 --compare
    python simulate.py --games 1000 --players 4 --ai random --override effects.king_draw=2
    python simulate.py --games 1000 --players 4 --ai random --csv results.csv
    python simulate.py --games 200 --players 4 --impact
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import sys
import tempfile
import time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai import AIBridge, RandomAI, GreedyAI, DefensiveAI, AIStrategy
from card import reset_uid_counter
from constants import ActionType, CardRank, CombinationType, load_config, reset_config_cache
from game import Game


AI_TYPES = {"random": RandomAI, "greedy": GreedyAI, "defensive": DefensiveAI}


class SimResult:
    def __init__(self):
        self.n_games = 0
        self.n_players = 0
        self.ai_type = ""
        self.total_rounds = 0
        self.rounds_list = []
        self.combo_counts = defaultdict(int)
        self.combo_scores = defaultdict(int)
        self.effect_play_count = defaultdict(int)
        self.wins_by_player = defaultdict(int)
        self.deck_exhausted = 0
        self.stalemate = 0
        self.winner_scores = []

    @property
    def avg_rounds(self):
        return self.total_rounds / max(1, self.n_games)

    @property
    def deck_exhausted_rate(self):
        return self.deck_exhausted / max(1, self.n_games)

    @property
    def stalemate_rate(self):
        return self.stalemate / max(1, self.n_games)


class _StatsBridge:
    def __init__(self, strategies, game):
        self._strategies = strategies
        self._game = game

    def log(self, text):
        pass

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
            source_idx, self._game.players, exclude, self._game)


def _apply_override(cfg, override_str):
    cfg = copy.deepcopy(cfg)
    for item in override_str.split(","):
        item = item.strip()
        if not item:
            continue
        key, val = item.split("=", 1)
        parts = key.split(".")
        d = cfg
        for p in parts[:-1]:
            d = d[p]
        try:
            val = int(val)
        except ValueError:
            try:
                val = float(val)
            except ValueError:
                pass
        d[parts[-1]] = val
    return cfg


def run_one_game(n_players, ai_cls, config_override=None):
    reset_uid_counter()
    reset_config_cache()

    if config_override:
        cfg = load_config()
        cfg = _apply_override(cfg, config_override)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(cfg, tmp)
        tmp.close()
        reset_config_cache()
        load_config(tmp.name)

    names = ["P{}".format(i) for i in range(n_players)]
    human_flags = [False] * n_players

    game = Game(bridge=None)
    strategies = {i: ai_cls() for i in range(n_players)}
    bridge = _StatsBridge(strategies, game)
    game.bridge = bridge
    game.setup(names, human_flags)

    try:
        game.run()
    except Exception:
        pass

    return game, bridge


def run_simulation(n_games, n_players, ai_type, config_override=None):
    ai_cls = AI_TYPES[ai_type]
    result = SimResult()
    result.n_games = n_games
    result.n_players = n_players
    result.ai_type = ai_type

    for _ in range(n_games):
        game, bridge = run_one_game(n_players, ai_cls, config_override)

        result.total_rounds += game.turn
        result.rounds_list.append(game.turn)

        if game.deck.is_empty:
            result.deck_exhausted += 1
        if "连续" in game.game_over_reason:
            result.stalemate += 1

        ranked = sorted(game.players, key=lambda p: p.total_score(), reverse=True)
        if ranked:
            result.wins_by_player[ranked[0].idx] += 1
            result.winner_scores.append(ranked[0].total_score())

        for p in game.players:
            for ctype, cards, score in p.scored:
                result.combo_counts[ctype.value] += 1
                result.combo_scores[ctype.value] += score
                for c in cards:
                    if c.is_effect or c.is_joker:
                        result.effect_play_count[c.rank.name] += 1

    return result


def analyze_effect_impact(n_games, n_players, ai_type):
    baseline = run_simulation(n_games, n_players, ai_type)
    baseline_avg = sum(baseline.winner_scores) / max(1, len(baseline.winner_scores))

    impact = {}
    for cfg_key, name in [("ace_draw", "ACE"), ("jack_hand_target", "JACK"),
                           ("queen_return", "QUEEN"), ("king_draw", "KING")]:
        override = "effects.{}=0".format(cfg_key)
        r = run_simulation(n_games, n_players, ai_type, config_override=override)
        no_avg = sum(r.winner_scores) / max(1, len(r.winner_scores))
        impact[name] = {
            "baseline_avg_score": round(baseline_avg, 2),
            "disabled_avg_score": round(no_avg, 2),
            "score_delta": round(baseline_avg - no_avg, 2),
            "baseline_avg_rounds": round(baseline.avg_rounds, 2),
            "disabled_avg_rounds": round(r.avg_rounds, 2),
            "baseline_stalemate_rate": round(baseline.stalemate_rate, 4),
            "disabled_stalemate_rate": round(r.stalemate_rate, 4),
        }
    return impact


def print_report(result):
    print("\n" + "=" * 60)
    print("  转牌 平衡性测试报告")
    print("=" * 60)
    print("  局数: {}    玩家数: {}    AI: {}".format(
        result.n_games, result.n_players, result.ai_type))
    print("-" * 60)
    print("  平均轮数:       {:.1f}".format(result.avg_rounds))
    if result.rounds_list:
        print("  轮数范围:       {} ~ {}".format(min(result.rounds_list), max(result.rounds_list)))
    print("  牌库耗尽率:     {:.1f}%".format(result.deck_exhausted_rate * 100))
    print("  僵局触发率:     {:.1f}%".format(result.stalemate_rate * 100))
    if result.winner_scores:
        print("  胜者平均得分:   {:.1f}".format(
            sum(result.winner_scores) / len(result.winner_scores)))

    print("\n  {:<16} {:>8} {:>8} {:>8}".format("牌型", "使用次数", "总得分", "平均分"))
    print("  " + "-" * 48)
    for ct in ["same", "straight", "flush_straight", "single"]:
        cnt = result.combo_counts.get(ct, 0)
        scr = result.combo_scores.get(ct, 0)
        avg = scr / max(1, cnt)
        print("  {:<16} {:>8} {:>8} {:>8.1f}".format(ct, cnt, scr, avg))

    if result.effect_play_count:
        print("\n  {:<16} {:>8}".format("效果牌", "打出次数"))
        print("  " + "-" * 28)
        for name, cnt in sorted(result.effect_play_count.items(), key=lambda x: -x[1]):
            print("  {:<16} {:>8}".format(name, cnt))
    print()


def print_impact_report(impact):
    print("\n" + "=" * 60)
    print("  效果牌影响分析 (禁用对比)")
    print("=" * 60)
    print("  {:<8} {:>8} {:>8} {:>8} {:>8} {:>8} {:>10}".format(
        "效果", "基准分", "禁用分", "差值", "基准轮", "禁用轮", "禁用僵局率"))
    print("  " + "-" * 70)
    for name, d in impact.items():
        print("  {:<8} {:>8.1f} {:>8.1f} {:>+8.1f} {:>8.1f} {:>8.1f} {:>9.1f}%".format(
            name, d["baseline_avg_score"], d["disabled_avg_score"],
            d["score_delta"], d["baseline_avg_rounds"], d["disabled_avg_rounds"],
            d["disabled_stalemate_rate"] * 100))
    print()


def save_csv(result, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["n_games", result.n_games])
        w.writerow(["n_players", result.n_players])
        w.writerow(["ai_type", result.ai_type])
        w.writerow(["avg_rounds", "{:.2f}".format(result.avg_rounds)])
        w.writerow(["deck_exhausted_rate", "{:.4f}".format(result.deck_exhausted_rate)])
        w.writerow(["stalemate_rate", "{:.4f}".format(result.stalemate_rate)])
        for ct in ["same", "straight", "flush_straight", "single"]:
            w.writerow(["combo_{}_count".format(ct), result.combo_counts.get(ct, 0)])
            w.writerow(["combo_{}_score".format(ct), result.combo_scores.get(ct, 0)])
        for name, cnt in result.effect_play_count.items():
            w.writerow(["effect_{}_plays".format(name), cnt])
    print("  CSV saved to {}".format(path))


def main():
    parser = argparse.ArgumentParser(description="转牌 平衡性模拟测试")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--players", type=int, default=4)
    parser.add_argument("--ai", default="random", choices=AI_TYPES.keys())
    parser.add_argument("--override", type=str, default=None)
    parser.add_argument("--csv", type=str, default=None)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--impact", action="store_true")
    args = parser.parse_args()

    t0 = time.time()

    if args.compare:
        for ai_type in AI_TYPES:
            print("\n>>> Running {} AI ...".format(ai_type))
            result = run_simulation(args.games, args.players, ai_type, args.override)
            print_report(result)
    elif args.impact:
        print(">>> Running effect impact analysis ({} games x 5 configs)...".format(args.games))
        impact = analyze_effect_impact(args.games, args.players, args.ai)
        print_impact_report(impact)
    else:
        result = run_simulation(args.games, args.players, args.ai, args.override)
        print_report(result)
        if args.csv:
            save_csv(result, args.csv)

    print("  完成, 耗时 {:.1f}s".format(time.time() - t0))


if __name__ == "__main__":
    main()
