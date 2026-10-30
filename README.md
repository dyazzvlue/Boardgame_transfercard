# TransCard / 转牌

Python 桌游引擎，规则见 [rule.md](rule.md)。

## 本地运行

```bash
python main.py --players 4 --ai 3 --ai-type greedy
```

使用 `python main.py --help` 查看参数。核心 CLI 不依赖 pygame。

## 联机模式

将本仓库与 `Boardgame_platform` 同级放置，或设置 `TRANSCARD_PATH`。
平台以独立包 `boardgame_transcard` 加载适配器，内部使用包内相对导入，
不修改 `sys.path`，不借用其他游戏的 `constants`、`card` 或 `online`。
游戏仓库与平台插件需一起更新。

引擎 `Game(bridge, rng=None)` 使用实例级 `random.Random`；
洗牌、效果牌和 AI 决策使用本局随机源，适配器不调用全局 `random.seed()`。
玩家视图仅含自己的手牌；缺省序列化、无效索引及观战索引 `-1` 只包含公开信息。

## 测试

已有 pytest 规则/效果测试位于 `test/`，模拟工具为 `test/simulate.py`。
模拟运行异常会向上传播并终止统计，不把异常中止的对局计为正常结果。
平台目录提供无额外测试依赖的适配器回归：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_game_plugins.py
```
