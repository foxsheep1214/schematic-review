# 夹具许可证

本目录的 `*.xml` 是第三方开源硬件原理图用 kicad-cli `sch export netlist --format kicadxml` 导出的网表
（前 33 块用 7.0.11，2026-10-19 新增的 9 块用 10.0.6），
只把 `<source>` 里的本机绝对路径换成仓库内的原理图相对路径，其余未改。它们是上游设计的衍生文件，
**不适用仓库根目录的 MIT 许可证**，各自沿用上游许可证；共享型许可证（CC-BY-SA-4.0、CERN-OHL-S-2.0、CERN-OHL-W-2.0、GPL-3.0）
要求以相同许可证再分发。完整 commit 与原理图路径见 `../sources.json`，版权归各上游作者。

| 夹具 | 上游仓库 | commit | 许可证 |
|---|---|---|---|
| rp2040-stamp.xml | solderparty/rp2040_stamp_hw | 6e66f7d09e7c | CERN-OHL-1.2 |
| esp32-c3-devkit-lipo.xml | OLIMEX/ESP32-C3-DevKit-Lipo | 5d93e79d46cf | CERN-OHL-S-2.0 (README) |
| rvpc.xml | OLIMEX/RVPC | 2b9675ba39c2 | CERN-OHL-S-2.0 (README) |
| fusb302-breakout.xml | cdg66/FUSB302_PCB | 7aab9ba5dd71 | MIT |
| powercb-usbc-ldo.xml | MartinWeigel/PowerCB | 15b8301fb2db | CC-BY-4.0 (README) |
| tps5430.xml | M4a1x/TPS5430 | 0b9cc6ced8c3 | CERN-OHL-S-2.0 |
| stepbubodc01.xml | mlab-modules/STEPBUBODC01 | baf771a5ab7e | GPL-3.0 |
| soldered-liion-charger.xml | SolderedElectronics/Li-ion-charger-hardware-design | 51d9df1bf15c | TAPR-OHL-1.0 |
| soldered-bq24295-charger.xml | SolderedElectronics/Li-ion-charger-BQ24295-with-5V-USB-output-board-hardware-design | 27ee43e29888 | TAPR-OHL-1.0 |
| soldered-liion-charger-protection.xml | SolderedElectronics/Li-ion-charger-with-protection-hardware-design | 6a5b7aff4dfd | TAPR-OHL-1.0 |
| piicodev-tmp117.xml | CoreElectronics/CE-PiicoDev-Precision-Temperature-Sensor-TMP117 | 426af09299dc | CC-BY-SA-4.0 |
| piicodev-ens160.xml | CoreElectronics/CE-PiicoDev-Air-Quality-Sensor-ENS160 | f49997cb62a0 | CC-BY-SA-4.0 |
| bme280-dspace.xml | Destination-SPACE/BME280-Breakout | 0313a25ea14f | CERN-OHL-P-2.0 |
| pmod-bme280.xml | fm4dd/pmod-bme280 | 4a4fca52203c | CERN-OHL-1.2 |
| soldered-txb0104-level-shifter.xml | SolderedElectronics/Logic-level-converter-generic-TXB0104-breakout-hardware-design | 245effc8223f | TAPR-OHL-1.0 |
| makerverse-motor-driver-2ch.xml | CoreElectronics/CE-Makerverse-Motor-Driver-2ch-Bipolar | 022864618d73 | CC-BY-SA-4.0 |
| piicodev-servo-driver.xml | CoreElectronics/CE-PiicoDev-Servo-Driver | 87214d7db5af | CC-BY-SA-4.0 |
| soldered-relay-1ch.xml | SolderedElectronics/1-channel-relay-board-hardware-design | 9c895d06b031 | TAPR-OHL-1.0 |
| esp32-4ch-relays.xml | leomanangka/esp32-4-channel-relays | 3c7d3b1eb80e | CERN-OHL-P-2.0 |
| isolated-serial-adapter.xml | Sirawit7205/isolated-serial-adapter | ec3f438c9712 | CERN-OHL-S-2.0 |
| han-to-rs485.xml | yyberi/han-to-rs485 | ad8068a57711 | CERN-OHL-P-2.0 |
| mcp25625-breakout.xml | asukiaaa/MCP25625-breakout | e3512dc777c6 | MIT (README) |
| soldered-can-mcp2518.xml | SolderedElectronics/CAN-Transceiver-MCP2518-board-hardware-design | 63d637a92c9e | TAPR-OHL-1.0 |
| bioamp-exg-pill.xml | upsidedownlabs/BioAmp-EXG-Pill | 86bb1f455750 | CERN-OHL-S-2.0 |
| makerverse-loadcell-hx710c.xml | CoreElectronics/CE-Makerverse-Load-Cell-ADC-HX710C | dcdcdcecab6f | CC-BY-SA-4.0 |
| lm386-amp.xml | ctes091x/lm386_amp | b477313d6cee | MIT |
| cmoy-headphone-amp.xml | designer2k2/kicad-cmoy | 6d214c4b896d | GPL-3.0 |
| led-al8860.xml | DIaLOGIKa-GmbH/pcb_constant-current-driver | 1c0a8bf7e34e | MIT |
| led-lm3404.xml | DIaLOGIKa-GmbH/pcb_constant-current-driver | 1c0a8bf7e34e | MIT |
| ethernet-pmod-lan8720.xml | swetland/ethernet-pmod | a9add2332c45 | CERN-OHL-P-2.0 |
| soldered-w5500.xml | SolderedElectronics/Ethernet-controller-W5500-board-hardware-design | b3d7a383d4e7 | TAPR-OHL-1.0 |
| makerverse-nano-power-timer.xml | CoreElectronics/CE-Makerverse-Nano-Power-Timer | 57f0569860de | CC-BY-SA-4.0 |
| usb232r02.xml | mlab-modules/USB232R02 | c48490f55fd4 | GPL-3.0 |
| flyback-viper22a.xml | MoElashmawi/Flyback-AC-DC-Converter | e49dd6d442a6 | MIT |
| flyback-uc3844.xml | gorkemguven/12V-1A-Isolated-Flyback-SMPS | 36a78f3d4086 | MIT |
| resonare-lcc.xml | Deco025/resonare | fb5771e206e9 | CERN-OHL-S-2.0 |
| moteus-c1.xml | mjbots/moteus（hw/c1） | 8f747f4ac448 | Apache-2.0 |
| bms-c1.xml | LibreSolar/bms-c1 | 0ca09706f499 | CERN-OHL-W-2.0 |
| easyiso.xml | Protocentral/protocentral_easyiso_hardware | 4b3fa114c8cb | CERN-OHL-P-2.0 |
| ideal-diode.xml | sparkfun/SparkFun_Ideal_Diode_Breakout | c950f439b55c | CC-BY-SA-4.0 (LICENSE.md, hardware) |
| pd-liion-charger.xml | MG-5/usb-c-to-liion-charger | 352e568fca17 | GPL-3.0 |
| pcm5102a-dac.xml | Giuseppe499/KiCad-GY-PCM5102A | 84c4329d53da | CERN-OHL-S-2.0 |
