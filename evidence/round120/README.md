# Round 120 evidence snapshot

这是第 120 轮“修虫子 v2”实验的精选、脱敏证据，不是全量实验目录。

## Files

- `frozen-decision-table.md`：结果产生前冻结的落格规则。
- `frozen-decision-table.sha256`：母库冻结记录的 SHA；导出时只把原中文文件名改为当前公开文件名，内容哈希未变。
- `result.md`：正式结果与边界。
- `controlled_validator.py`：从历史验证器修出的公开版受控判卷器；修复清单见 `KNOWN_ISSUES.md`。
- `tests-public.json`、`tests-held-out.json`：自造题；后者只在第 120 轮运行时私持，随证据快照公开后不再能充当未来实验的隐藏集。
- `starting-best.json`：三臂共同起点。

## Security warning

验证器会导入并执行候选 Python。它有 AST 检查、超时、两遍确定性检查和强制 `unshare -n`，但仍不是文件系统安全沙箱。它默认拒绝执行，且隔离不可用时失败关闭。只在隔离容器里对可信的受控实验候选使用；不要在宿主机上执行任意第三方代码。

## Result boundary

正式落格是三臂打平。这个快照证明的是实验装置、冻结纪律和负结果披露，不证明 `ctx-key` 已提高任务成功率。

## Local checks

```bash
sha256sum -c frozen-decision-table.sha256
```

验证器不进入默认本地检查或 CI。若在隔离容器内重放可信候选，仍需显式传入 `--i-understand-this-executes-code`；共同起点不会推进分数。

## Glossary

- `frozen-decision-table.md` 第 12 行「28/3/18 题构成」是冻结时从任务书原样引用的常量，含义为：**公开题 28 道，其中只有 3 道在题面公开期望值示例（其余公开题不给答案）；另有私持题 18 道**。判卷总分 28＋18＝46。它不是算术求和，特此说明（冻结表本身不可改动，故勘误记在这里）。
