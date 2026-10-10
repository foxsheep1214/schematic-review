# 夹具许可证

本目录的 `*.xml` 是第三方开源硬件的 ASG 重画/生成交付经 KiCad 原生导出、再由 `make_fixtures.py`
精简后的网表。它们是上游设计的衍生作品，**不适用仓库根目录的 MIT 许可证**，各自沿用上游许可证；
共享型许可证（CC-BY-SA-4.0、CERN-OHL-S-2.0）要求以相同许可证再分发。来源 commit 与哈希见 `../sources.json`。

| 夹具 | 上游 | commit | 许可证 | 署名 |
|---|---|---|---|---|
| r01-thingplus-esp32s3.xml | sparkfun/SparkFun_Thing_Plus_ESP32-S3 | c9fc69f | CC-BY-SA-4.0 | SparkFun Electronics；schematic designed by N. Seidle |
| r02-dasduino-coreplus.xml | SolderedElectronics/Dasduino-COREPLUS-hardware-design | 594827b | TAPR Open Hardware License 1.0 | Soldered Electronics |
| r03-nrf9151-feather.xml | circuitdojo/nrf9151-feather | 43c5345 | CERN-OHL-S-2.0 | Circuit Dojo |
| r04-host-usb-pmod.xml | sparkengineering/host-usb-pmod | f8b902a | CERN-OHL-P-2.0 | sparkengineering |
| r04-c1-return-moved.xml | 同上（门禁反例的编辑副本） | f8b902a | CERN-OHL-P-2.0 | sparkengineering |
| r05-lipo-charger.xml | bablokb/pcb-lipo-charger | 5a9ef45 | CC-BY-SA-4.0 | bablokb（GitHub 账户） |
| rh-ad8495-thermocouple.xml | SolderedElectronics/Thermocouple-sensor-AD8495-breakout-hardware-design | 43ac86f | TAPR Open Hardware License 1.0 | Soldered Electronics |

修改说明（各许可证要求注明）：电路由 ASG 按上游原理图重画或按需求重新生成，位号和图页可能与上游不同；
精简时删去了标题栏、数据手册与描述文字、时间戳、库列表、非 dnp 属性和非 MPN 字段，连接关系、
引脚名与类型、器件值和封装未改。这些网表只用于回归评测，不能当作上游设计的权威版本或可生产文件。

`rh-ad8495-thermocouple.intent.json` 是本仓库作者写的审查输入（MIT），其中的脚表内容引用
ADI AD8494/5/6/7 Rev.D 与 TI SLVS543S 的引脚定义。
