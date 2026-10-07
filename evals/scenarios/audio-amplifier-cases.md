# Analog Class-D audio module: bounded checks

Source: CoreElectronics/CE-Makerverse-PAM8302-Class-D-Amplifier,
commit `c18a15da1183edf1132b8eb2070f28d5e84bdead`, title date2021-11-16,
CC BY-SA4.0 hardware. PAM8302AAD/SO8, DS41333 Rev6-2 and source2013 PDF;
raw inputs, calculations and independent review archived in round-09 of
campaign2026-10-07-restart. These are manual paired cases, not new rules.

| Case | Correct or bounded branch | Fault or unknown branch |
|---|---|---|
| Continuous power budget (G1/G4) | 1W/5.5V/350mA passes the necessary energy bound only | Author2.5W/5.5V with350mA max contradicts steady-state energy even at100% efficiency; clarify continuous/peak conditions, do not claim every audio transient draws this lower bound |
| Supply conditions (G3/G4) | 5V lies in the stated2..5.5V table window, not proof of all-temperature power | Author1.8V claim is below both tabular minima; typ application1.8 and descriptiveUVLO2.1 conflict internally, so preserve the discrepancy and obtain guaranteed low-voltage startup/recovery rather than invent a cutoff |
| Continuous volume (G3/G4) | For ideal low-Z source,50k pot and nominal10k input, Rth spans0..12.5k and loaded attenuation must include the IC input | Half rotation is not half output: nominal total gain is3.33 rather than7.5; unknown source/tolerances cannot establish a promised precision window, and no unspecified flat-band target is a defect |
| BTL polarity and return (G2/G5) | IN- excitation plus intentionally reversed output silk can preserve acoustic sign; both J2 legs are driven | Grounding either BTL leg is a real forbidden connection; different VO/speaker naming alone is not a wiring defect, nor does an integrated speaker bridge require a relay flyback diode |
| Output filter choice (G4/G6) | SourceNP0 note and author's comparative distortion test justify investigating1n rather than imposing the220p example constant | A generic0805 bead proves neither current/DCR nor impedance; sinusoidal2.5W/4ohm gives0.791Arms/1.118Apeak only, not PWM capacitor current or actual speaker impedance qualification |
| Shutdown and startup (G3/G5) | R1 pulls SD to its own rail; SD low disables the chip while R1/LED can still draw board current | A chip1uA shutdown bound is not board standby total; pop-delay recommendations become conditional host advice unless pop performance was required, and AC coupling blocksDC but not off-state transient injection |

Keep connection, nominal model, procurement qualification and downstream
audio/EMC/thermal evidence separate. Same-family5V playback and a1kHz test
jig are useful positive evidence, not commit-bound full-corner acceptance.
Do not lower limits or count these cases as measured accuracy improvement.
