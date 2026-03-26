"""CLI text interface for TransCard (转牌)."""

from __future__ import annotations

from constants import ActionType

_ACTION_LABELS = {
    ActionType.DRAW_DECK: "从牌库抽牌",
    ActionType.DRAW_PLAYER: "从玩家手里抽1张",
    ActionType.RETURN_AND_DRAW: "放1张到牌库底，摸1张",
    ActionType.PLAY_CARDS: "打出牌型",
}

_current_game_ref = None


def set_game_ref(game):
    global _current_game_ref
    _current_game_ref = game


class CLIBridge:
    def log(self, text):
        print(text)

    def show_state(self, game):
        print("\n--- 牌库剩余: {}  弃牌堆: {} ---".format(game.deck.remaining, game.discard.size))
        for p in game.players:
            tag = " <- 当前" if p.idx == game.current_idx else ""
            print("  {}: {}张手牌, {}分{}".format(p.name, p.hand_size(), p.total_score(), tag))

    def ask_action(self, player_idx, available):
        print("\n可选行动:")
        for i, act in enumerate(available):
            print("  {}. {}".format(i + 1, _ACTION_LABELS[act]))
        while True:
            raw = input("选择行动 (输入编号): ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(available):
                return available[int(raw) - 1]
            print("无效输入，请重试")

    def ask_select_cards(self, player_idx, purpose, n=None):
        player = _current_game_ref.players[player_idx]
        hand = player.hand

        if not hand:
            return []

        print("\n{} 的手牌:".format(player.name))
        for i, c in enumerate(hand):
            print("  {}. {}".format(i + 1, c.short_name()))
        print("目的: {}".format(purpose))

        if n is not None:
            prompt = "选择{}张牌 (用逗号分隔编号): ".format(n)
        else:
            prompt = "选择要打出的牌 (用逗号分隔编号; 输入0放弃): "

        while True:
            raw = input(prompt).strip()
            if raw == "0":
                return []
            try:
                indices = [int(x.strip()) - 1 for x in raw.split(",")]
                if all(0 <= idx < len(hand) for idx in indices):
                    if n is not None and len(indices) != n:
                        print("需要选择正好{}张牌".format(n))
                        continue
                    if len(set(indices)) != len(indices):
                        print("不能选择重复的牌")
                        continue
                    return [hand[idx] for idx in indices]
            except ValueError:
                pass
            print("无效输入，请重试")

    def ask_select_player(self, source_idx, prompt, exclude=None):
        players = _current_game_ref.players
        exclude = exclude or []
        candidates = [p for p in players if p.idx not in exclude]

        print("\n{}".format(prompt))
        for i, p in enumerate(candidates):
            print("  {}. {} ({}张手牌)".format(i + 1, p.name, p.hand_size()))
        while True:
            raw = input("选择玩家 (输入编号): ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(candidates):
                return candidates[int(raw) - 1].idx
            print("无效输入，请重试")
