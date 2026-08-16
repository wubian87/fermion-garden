# Round 122 evidence snapshot（预注册阶段）

这是第 122 轮"死路记录渲染写法三臂"实验的证据目录。**本轮跑数尚未开始**：本目录于点火前推送，作为先于见数的外部时间戳，流程见 [../../docs/preregistration.md](../../docs/preregistration.md)。

## Question

同一道修虫子题（第 120 轮冻结卷原封）、同一种全量读法，三臂只差「已验证的死路记录」渲染写法：尺＝判断边界【判线】／画＝现象预告【预告】／禁＝禁令 ⛔【禁走】（与第 121 轮禁臂文案逐字相同，作对照臂）。主判标重踩率 R；白跑率 Z 作副。

## Files

- `frozen-decision-table.md`：结果产生前由未看数据的独立判据表作者写死的落格规则（三臂对称重跑、开格对预注册、收口机制格表与判词模板）。
- `frozen-decision-table.sha256`：母库冻结记录的 SHA；导出时只把原中文文件名改为当前公开文件名，内容哈希未变。

**结果未产生：本目录于点火前推送，见 [../../docs/preregistration.md](../../docs/preregistration.md)。**

自造题、受控判卷器与三臂共同起点均与第 120／121 轮同一套，不重复收录：题与起点见 [../round120/](../round120/)，判卷器见 [../round120/controlled_validator.py](../round120/controlled_validator.py)；同轴上一轮（描／禁双臂）见 [../round121/](../round121/)。

## Local checks

```bash
sha256sum -c frozen-decision-table.sha256
```
