# TransCard（转牌）开发规范与优化记录

本文件记录转牌项目的架构决策、开发规范和平衡性优化历史，
供 AI 编程助手在此项目中工作时参考。

---

## 项目结构

```
TransCard/
├── tmp_rule.md          游戏规则文档（权威规则来源）
├── constants.py         枚举定义 + 配置加载
├── card.py              Card / Deck / DiscardPile 数据模型
├── rules.py             纯函数：牌型验证、计分、效果触发计算
├── player.py            Player 状态（手牌 + 计分区）
├── effects.py           效果注册表（@register_effect 装饰器）
├── game.py              主游戏引擎（bridge 模式）
├── ai.py                3 种 AI 策略 + AIBridge 适配器
├── ui.py                CLI 文本界面
├── main.py              入口点
├── data/
│   └── config.json      所有可调参数（标记为 (x) 的值）
├── test/
│   ├── test_rules.py    规则单元测试（45 条）
│   ├── test_effects.py  效果单元测试（13 条）
│   └── simulate.py      自动化平衡性模拟工具
└── skill/
    └── TransCard_dev_skill.md  本文件
```

---

## 架构原则

1. **Bridge 模式解耦 I/O**：`game.py` 通过 bridge 接口交互，不直接处理输入输出。CLIBridge（人类）、AIBridge（AI）、未来的 NetBridge（联机）可互换。
2. **效果注册表模式**：每个效果牌是独立函数，用 `@register_effect(CardRank.X)` 注册。修改/新增效果只改 `effects.py`，不影响其他模块。
3. **纯函数规则层**：`rules.py` 中所有函数无副作用，只做判断和计算，便于测试。
4. **配置驱动**：所有数值参数在 `data/config.json`，代码通过 `load_config()` 读取，模拟工具通过 `--override key=val` 临时覆盖测试。

---

## 关键设计决策

### 牌型判断
- A 在顺子中两端可用：A23✓、QKA✓、KA2✗
- 同色 Joker 可配对（红+红✓，黑+黑✓，红+黑✗）
- 同花顺最少 5 张，效果触发翻倍（头尾 ×2）
- 顺子效果牌只触发头尾位置

### 效果结算
- 多次触发逐次结算（如 K 触发 2 次 = 所有人摸 1 张 → 再所有人摸 1 张）
- 指定玩家的效果每次独立选择目标
- 出牌后先结算效果，再检查游戏结束

### 行动经济（当前值）
| 行动 | 手牌变化 |
|------|----------|
| 摸牌 | +1 |
| 抽人 | +1（对方-1） |
| 换牌 | +1（-1+2） |
| 出牌 | -N+1 |

### 计分区
- 每个玩家有独立计分区，存放已打出的牌型
- 游戏结束时只算计分区的分，手牌不算分

---

## AI 策略

| 策略 | 行为 |
|------|------|
| RandomAI | 随机选择行动和牌 |
| GreedyAI | 只打 ≥2 分的组合，否则摸牌 |
| DefensiveAI | 有组合就出（优先多张），尽快清手牌 |

**已知问题**：GreedyAI 在牌库耗尽后仍有 ~47% 僵局率（拒绝出低分牌导致死循环），这是 AI 策略缺陷而非规则问题。

---

## 模拟工具使用

```bash
# 基础模拟
python test/simulate.py --games 500 --players 4 --ai random

# 三种 AI 对比
python test/simulate.py --compare --games 500

# 效果牌影响分析
python test/simulate.py --impact --games 500

# A/B 测试（临时覆盖配置值）
python test/simulate.py --games 500 --players 4 --override "scores.same.2=3,game.stalemate_rounds=3"

# 输出 CSV
python test/simulate.py --games 1000 --csv results.csv
```

---

## 平衡性优化历史

### v1 → v2：行动收益均衡化
**问题**：摸牌 +2 碾压一切，换牌 ±0 无意义，出牌是纯亏。
**改动**：
- 摸牌：2 → 1 张（`draw_count: 1`）
- 换牌：还1摸1 → 还1摸2（`return_draw_count: 2`）
- 出牌后补牌：新增摸1张（`play_draw_count: 1`）
**结果**：所有非出牌行动统一 +1，出牌惩罚减轻为 -N+1。

### v2 → v3：得分体系平衡
**问题**：
- 单打 Joker 效率 3~5 分/张，碾压所有牌型
- 对子 1 分/2 张 = 0.5 分/张，性价比最低
**改动**：
- 对子得分：1 → 2 分（`scores.same.2: 2`）
- 单打 Joker 独立分值：红 5→3 / 黑 3→2（`joker_red_single: 3`, `joker_black_single: 2`）
- 多张 Joker 保持原值（红5/黑3每张）
**结果**：single 均分从 4.0 降到 2.5，same 均分从 1.2 升到 2.1，与 straight 2.5 趋于收敛。

### v3 → v4：效果牌重设计
**问题**：
- Q 是负收益效果（禁用后分数反而 +0.4），因为自己也要还牌
- J 几乎无感（禁用后分数变化仅 0.1），因为手牌数本来就接近目标值
**改动**：
- Q 改为只影响其余玩家（排除出牌者），出牌者不再自伤
- J 改为从 2 名玩家各盲抽 1 张，保留 0~1 张，其余放回牌库底
**结果**：
- Q 禁用差从 -0.5 变为 +0.1（不再是负收益）
- J 禁用差从 +0.1 变为 +0.5（有了明显正收益）

### 当前平衡数据（4P random，500局）
| 指标 | 值 |
|------|------|
| 平均轮数 | 35 |
| 僵局率 | 6.2% |
| 牌库耗尽率 | 84% |
| 胜者平均得分 | 19.0 |
| same 均分 | 2.1 |
| straight 均分 | 2.6 |
| single 均分 | 2.5 |
| flush_straight 均分 | 10.0 |

---

## 待办事项

- [ ] Greedy AI 牌库空时降低出牌阈值（修 AI 策略）
- [ ] 同花顺出现率极低（500局约13次），可考虑降门槛或提高奖励
- [ ] gameplatform 联机适配（adapter.py / state.py / _ui_shim.py / plugin.py）
- [ ] 前端渲染器（transcard.js）

---

## 编码约定

- Python 3.7+ 兼容（使用 `from __future__ import annotations`，避免 `X | Y` 类型语法）
- 字符串格式化使用 `.format()` 而非 f-string（兼容性）
- 配置值通过 `cfg.get("key", default)` 读取，新增配置需提供回退默认值
- 测试中使用 `reset_uid_counter()` 和 `reset_config_cache()` 确保隔离
