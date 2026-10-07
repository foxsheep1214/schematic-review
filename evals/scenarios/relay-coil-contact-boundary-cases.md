# Relay coil/contact evidence boundaries

Source: SolderedElectronics/1-channel-relay-board-hardware-design@9c895d06b031ebd2fdfd5b06d9c940866e444e1c, editableV1.1.1. Human paired cases; only NC-contact lint behavior is executable below. Available historical author-linked Songle FORM C sheet differs from new manufacturer V1; neither identifies the actual supplied lot.

| Evidence | Correct disposition | Paired counterexample |
|---|---|---|
| Classified fitted FormC relay, unique NC/COM/NO on three independent nets; NC routes only real connectors/compatible NC contacts | NC means normallyclosed, do not infer NoConnect short from net name. Check real ratings separately | Semiconductor NC mixed in net, missing roles, NC/NO short or K-prefix alone: retain NET-A04 candidate. Export pseudoNC stays INFO |
| K2 VCC5V vs IN3.3–5V, current author family VCC table says3.3/5 | Record current documentation contradiction; selected2021 circuit supply scope remains5V | Do not invent a2021 physical3.3V failure from a later family page or guarantee pickup from logic voltage |
| U1 inputcathode and Q1emitter share GND | No galvanic isolation across opto/driver; actual barrier is relay coil/contact | Isolated-looking symbol or broad README assurance is not actual isolated ground/PCB clearance proof |
| PC357 CTRmin50% IF5mA/VCE5V/25C; emitterfollower base drive has330ohm collector supply resistor | Qualify actual IF/VCE/Q1IB/temperature/aging jointly | Multiplying arbitrary IF by50%, or VCEsat.2V at a different IC, is not guaranteed coil pickup |
| 100ohm input at5V: V/R loose upper may exceed50mA; actual diodeVF/inputsource unknown | INSUFFICIENT local input/part rating; not confirmed overstress from a loose bound | Typical1.2V or assumed0603power is not guaranteed safe/unsafe; qualified180ohm candidate bounds stress but reduces drive |
| D2 directly spans coil, R4 lies upstream | Correctly orient flyback loop and review D2 repetition/VF/rating | A directVCC-only clamp heuristic miss is not a confirmed missing diode; blueLED can see D2VF reverse stress |
| Manufacturer release≤5ms explicitly WITHOUT DIODE | Do not extend to actual diode-clamped board release | LEDOUT state does not prove mechanical contact state or release timing |
| Historical FORM C7A28VDC/7A240VAC vs FORM A10A and newV1 selectable7/10/15A family | Bind actual C-form lot/version/load/ambient; retain qualification gap | No FormA borrowing, independent maximum current/voltage multiplication, or silent old/new rating merge |
| Actual module pin mapping proven by SCH/PCB/same-versionPDF; K3 working ratings unknown | DEV-E01 mapping PASS; DEV-C04 connector rating INSUFFICIENT | Missing rating does not undo proven pin map. One R1/MOS change cannot close independent contact/terminal load task |
| Unimplemented AO3400A+1kohm gate series/100kohm pull-down candidate,48mohm bound onlyTj25/VGS2.5 | Conditional alternative removing optoCTR/BJT identity dependencies after full approved re-review | Do not claim125C/VGS2.5 guarantee from10V row, invent official pin numbers, or guarantee HiZ using different leakage test conditions |

Executable counterpart: `scripts/tests/test_relay_nc_contact.py`. Its negative cases preserve actual no-connect candidates; suppression is not an electrical PASS or hardware release. Human cases do not claim measured automatic electrical-detection benefit.
