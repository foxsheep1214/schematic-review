# 真实来源的网表导入回归

此工具只比较**导入完整性**。不新增电气规则，不把原件作为整板合格答案，不计算真实设计准确率。

`rtc-v1.manifest.json` 冻结 Sergey Kiselev RTC V1.0 的公开来源 commit、GPL-3.0、作者网表哈希，以及确定性语法转换的 XML 输入哈希、6 个器件值和 29 个物理脚的 11 个网络分区。转换保留原件网络名、连接、值和原库类型；不恢复 NC 标记、不修库类型，不是现代 KiCad 原生导出或 ERC 通过。原件保留在项目的公开电路校准目录，不打包到技能仓库。其他使用者可以从 manifest 的冻结 raw_url 下载作者网表，再运行下列语法转换；下载时保留作者许可证。来源与限制见[RTC人工判例](../scenarios/rtc-backup-cases.md)。

```sh
python3 evals/input_bench/adapt_author_net.py /作者原网表/rpi_rtc.net \
  --expected-sha256 af0a17f4a109e69a91406968513a525dccb166c72d6cdb18b5aaba83844d7ccf \
  --out /tmp/codex-work/本任务/rtc-author.xml
python3 evals/input_bench/run.py --input /tmp/codex-work/本任务/rtc-author.xml \
  --manifest evals/input_bench/rtc-v1.manifest.json --out /tmp/codex-work/本任务/after.json
python3 evals/input_bench/run.py --input /tmp/codex-work/本任务/rtc-author.xml \
  --manifest evals/input_bench/rtc-v1.manifest.json --scripts /旧版本/scripts \
  --out /tmp/codex-work/本任务/before.json
```

输入必须精确匹配冻结 SHA256，缺文件/不匹配属于 BLOCKED，不能算测试完成。测试原图分区/值保持，以及从该冻结输入生成的三种结构故障：空导出、重复位号、同一物理脚归入多个网。故障变体是合成输入，不能称三个新增真实项目。输出新文件，不覆盖旧结果；任一不符合预期退出 3。

改进前空导出已可由下游 `self_check` 拦截；现在在 `parse_kicad.parse` 边界直接拒绝，并阻止重复身份和节点被字典静默覆盖。评分明确只测解析入口，不把入口改善冒充此前整板误放行被修复。

接入其他授权实板时先独立核对原始图/作者网表及分区和值，保存来源与 SHA256，然后另建 manifest。不要把待审电气结论写成金标准，也不要原地换旧输入/答案。合成边界用例在 `scripts/tests/test_import_integrity.py`，既有功能校准与 Circuit Bench 仍单独保留。
