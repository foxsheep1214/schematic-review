# brainsmoke--usb2_hub / lane-1

来源：brainsmoke/usb2_hub @ `a6288e2ffc48`，CC-BY-4.0；用途**推断**为USB-C上行、4×USB-A、FE1.1 MTT Hub，独立AP22652A开关及USBLC6 ESD。基线industrial_telecom，补CLOCK/STARTUP。KiCad10.0.7 strict成功，95件/301端点/5页；XML↔db零差异，同提交BOM94件，J6原生DNP。

| 计划项 | 局部已判 / 逐ID待核 | 发现根因 | 真缺陷 | 误报 | 准则问题 | 知识缺口 | 人工 | 漏报模式 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 688（683+补5） | 101 / 587 | 27 | 2 | 11 | 1 | 4 | 9 | 1（5个ESD位点） |

**门禁FAIL / valid=false / NO_GO。** 101项=78 PASS、21 NA、2 FAIL，均为局部结论；45功能框架未全部审结。原生报告仅诊断，未打包，不支持冻结；原生“资料不足0”不代表587项审完。27条为12条非INFO扫描逐条归因及15条独立观察，不是27个板上缺陷。

1. **优先合并：多通道ESD保护端口建模。** `protected_net`只收2网且依赖型号词，U6-U10六网阵列虽已核TVS仍无PRO-E02；须按官方馈通针表枚举I/O和VBUS。M01已合法补问5项，工作窗/钳位/事件仍待证；不把计划漏问写成实物失效。
2. **J5真实入口电容偏离。** C5-C8/C30五只10µF及五只100nF直接挂VBUS，名义50.5µF；准确C15850即使只取五只零偏压下界也45µF>Type-C非Attached的10µF（2.5版p153/2.0版p142）。另一真缺陷是首页R5/R6文字叠印。下行22.1µF不能机械按“每口120µF”判错；原厂资料有“每Hub”口径，需结合开关/压降。
3. **六个电气误报可重复。** VS_PLL10/VS_A25官方是地，OVCB四脚官方是输入；不能由native power_in或符号output越过已核官方脚表。G01-031也必须保留Type-A默认VBUS例外（Type-C2.5 p152）。

SR用法：R8 `2K7 (1%)`可独立读成2.7k±1%，解析器却拒；AP22652A须按p12 A锁存后缀核，不照缓存符号名；HardwareWiki名SC6文件实为SC6Y，准确SC6在`ST - USBLC62.pdf`。schema15不收needs_human/未定产品合同，故保存逐ID pending及全部45框架旁账并保留FAIL，不伪造VENDOR_DATUM或整功能PASS。报告索引未打包，完整账本请读[审查缓存](/Users/skyfend/.cache/sr-boards/brainsmoke--usb2_hub/review)；[归因](findings.json)、[50条核对](top50-audit.json)。
