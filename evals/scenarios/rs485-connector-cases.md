# RS485 module: connector roles and bounded guarantees

Source: SolderedElectronics/RS-485-Transceiver-breakout-hardware-design,
commit `22fb2d67cd4cd06996c4f092d209308e0b192f56`, V1.0.0 native/PDF/BOM,
TAPR OHL 1.0. TI SN65176B SLLS101I (August 2025); source bytes and complete
review are archived in calibration campaign 2026-10-07-restart/round-08.
This is an open TTL-to-RS485 module in design iteration, not a host/cable
system or a manufacturing release. V1.1.0 outputs are a separate comparison.

* K1 `TERMINAL_KF235-5.0-3P` and K2 `HEADER_MALE_6X1` are connectors,
  confirmed by the native pins and schematic. Explicit connector families
  must override the K-prefix relay guess and expand pin mapping, opposite-end
  semantics, unused-pin disposition and external protection checks. A bare K
  or a part explicitly naming a relay must still retain coil candidates;
  no connector keyword supplies a pinout or a current rating.
* U1 pins are R1, active-low RE2, DE3, D4, GND5, A6, B7, VCC8.
  Keep this physical/function mapping distinct from wrong source pin types
  (K1 input and U1 GND power_out). Parser metadata repair must preserve
  original bytes and every component/net/pin edge. Native ERC errors remain
  recorded; a parseable derived file is not an ERC pass.
* Author README claims 20 Mbps and 120–500 uA. TI supports 10 Mbps and lists
  no-load disabled ICC 26 mA typical / 35 mA maximum, enabled 42 mA typical
  with differing 70/55 mA maxima in driver/receiver tables. These are two
  document/specification conflicts; typical current is not a guaranteed
  lower bound and the larger maximum is not full-board loaded current.
* Own 20k/20k bias and closed 120R termination give 14.96 mV at nominal 5V
  before leakage, below the receiver +200 mV guaranteed-high threshold.
  Record the missing autonomous idle guarantee and integration constraints.
  Do not invent a failsafe requirement or mark every module failed. Opening
  JP2 removes only this termination; other nodes/termination remain relevant.
* R2's 120R/0603 label does not establish power rating. A 5.25V conservative
  envelope gives 229.7 mW nominal; obtain actual tolerance, power/derating and
  applicable drive/load conditions. Do not declare overload from a generic
  0603 rating. R1/R4 also see bus common-mode voltage: at bus -7..12V their
  respective nominal-resistance envelopes reach 7.2/7.50 mW, not merely the
  5.25V rail-only estimate. Unknown passive qualification is not solved by
  assuming arbitrary manufacturer data.
* Four JP1/JP2 configurations retain the same U1 supply and TTL connections.
  Export host logic/voltage/reset/off-state and endpoint termination limits;
  an unbound 115200-baud vendor example is positive usage evidence but does
  not prove this commit, all-high-Z idle, 20 Mbps, 1200 m or an IEC class.

Reproduce role/plan/safety counterexamples with
`python3 -B scripts/tests/test_connector_roles.py`. Keep the true relay
without a clamp reporting DRV-A01, along with conservative unknown-K and
declared-relay cases. Runtime changes require the full frozen review to be
regenerated and re-reviewed; test counts are not calibration quality scores.
