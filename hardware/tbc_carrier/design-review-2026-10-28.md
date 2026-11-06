# Clacktronics TBC carrier design review

Date: 28 October 2026. KiCad 10.0.3; single-sheet carrier; 62 × 58 mm, four copper layers, nominal 1.6 mm thickness.

**Verdict: not ready for fabrication.** The schematic architecture is plausible, but the current PCB has unfinished supply, ADC-reference and signal connections. A zone refill removes stale-fill collisions but does not repair those open connections or the remaining clearance errors. Do not release the existing fabrication archive as a finished design.

This review covers the current `tbc_carrier.kicad_sch`, `.kicad_pcb`, `.kicad_pro`, existing Gerbers/drills, BOMs, socket mapping, and ADC-interface RTL. It is a design review, not a routing edit. The schematic and PCB source hashes remained unchanged.

## Prioritized findings

| ID | Priority | Finding and action | Confidence / evidence |
|---|---|---|---|
| DR-01 | Critical | **17 open connections remain after refill**, including +5V, +3V3, +3.3VA, U2 VREF/REFTS and REFBF. Complete all native DRC connection items before power-up or fabrication. | High; native KiCad DRC, raw PCB and native schematic netlist |
| DR-02 | Critical for current release | **Saved zone fills overlap newly placed/routed items.** Ten zone-clearance and four mask-bridge errors disappear after an in-memory refill. Refill and save after routing, then regenerate fabrication outputs. | High; before/after native DRC comparison |
| DR-03 | Fabrication blocker | **R2–TP1 clearance is 0.1296 mm**, below the 0.2 mm net-class rule; their courtyards also overlap. **R28 pad 1–GND via clearance is 0.15 mm**, also below 0.2 mm. Move the affected items and recheck. | High; native DRC after refill |
| DR-04 | Warning | U1 schematic/BOM selects **CBM8051NST6**, but PCB Value remains **OPA355NA** and Manufacturer remains Texas Instruments. Synchronize fields before regenerating assembly files. Pin numbering is compatible; this is a document/assembly inconsistency, not evidence of swapped pins. | High; cross-domain analyzer, native parity and manufacturer pinout |
| DR-05 | Warning | ADC clamp pulse is **40 clocks = 1.481 µs**, versus **2 µs typical** in the MS9280 table. R7 × C8 = **22 µs**. Validate acquisition over successive lines and line droop; do not treat a digital-only simulation as clamp validation. | Medium; RTL, calculation, MS9280 PDF pp. 7, 15–16; 2 µs is typical, not a stated minimum |
| DR-06 | Warning | External ADC capture has no supplied worst-case timing constraints. `--freq 27` and internal timing closure do not establish ADC-to-FPGA setup/hold margins. Add a justified external timing budget and test capture phase. | High for missing constraints; performance consequence needs characterization |
| DR-07 | Warning | HGSEMI LM1881 operation is specified from **5 V**. A nominal USB-derived 5 V rail can fall below this at U4 under cable and load drop. Characterize minimum U4 supply, or select a supply/part with guaranteed low-voltage margin. | Medium; exact HGSEMI PDF p. 5 and J2.40 power topology; actual supply minimum not specified |
| DR-08 | Assembly cleanup | Native DRC reports **74 silkscreen-over-copper and 60 silkscreen-overlap warnings**. Review critical pin-1, connector and test-point markings. No board fiducials were found; agree panel fiducials/alignment with the assembler. | High for counts; assembly requirement depends on process |

## Native ERC and DRC

| Check | Saved board | In-memory zone refill |
|---|---:|---:|
| Open connection items | 17 | 17 |
| Copper clearance errors | 12 | 2 |
| Solder-mask bridge errors | 4 | 0 |
| Courtyard overlap errors | 1 | 1 |
| Dangling-track warnings | 4 | 4 |
| Silkscreen warnings | 134 | 134 |
| Schematic parity warnings | 2 | 2 |

ERC reports **zero violations** under the project’s configured checks. It does not check actual board routing or device behavior. DRC initially aborted in the sandbox; the same native tool completed outside it. The refill was performed in memory without `--save-board`.

Evidence: [saved-board DRC](analysis/native/drc.json), [refilled DRC](analysis/native/drc-refilled.json), [ERC](analysis/native/erc.json).

### Open connections to fix

The 17 DRC items group as follows; a DRC pair describes two disconnected copper groups, not necessarily the only possible routing endpoints.

| Net / circuit | Items | Representative disconnected endpoints |
|---|---:|---|
| +5V | 2 | Separate front-end/source/sync-supply track groups |
| +3V3 | 2 | U5.8 and disconnected 3.3 V track groups |
| +3.3VA | 1 | Track at (144.0765, 127.575) and track at (142.9, 130.825) |
| VREF | 1 | U2.26 ↔ U2.21; top-reference connection is incomplete |
| REFBF | 1 | Reference-decoupling track ↔ U2.24 |
| AD_OTR | 1 | U2.13 ↔ OTR track |
| ADC_CLAMP | 1 | Clamp track ↔ TP4; at minimum the test-point branch is disconnected |
| ADC D0 path | 2 | U2.3 ↔ R28.1 and R28.2 ↔ J2.30 |
| ADC D1 path | 2 | U2.4 ↔ R27.1 and R27.2 ↔ J2.4 |
| Reference composite sync | 1 | U4.1 ↔ U5.1 |
| Reference vertical sync | 3 | U4.3 ↔ U5.6; U5.2 ↔ R17.1; R17.2 ↔ downstream REF_VSYNC group |

The current RTL consumes only ADC bits [9:2], but that does not make the supply/reference gaps benign, nor does it make the intended 10-bit interface complete. The separate REF input is not currently consumed by `top.v`; its incomplete routing still prevents the carrier’s advertised expansion function.

## Component summary and verification basis

79 physical components: 28 resistors, 26 capacitors, 5 ICs, 4 connector symbols, 2 inductors, 2 protection diodes, 1 ferrite, 2 jumpers, 5 test points, and 4 mounting holes. There are 82 placed non-power symbol units because U5 has four units, and 79 PCB footprints. These are consistent counts.

The independent audit compared **all 236 net-assigned schematic pins with all 236 PCB pad assignments** and found no net-assignment mismatch. It also compared analyzer connectivity partitions with the native KiCad XML netlist and found no discrepancy. This establishes internal consistency, not that copper physically connects the pads.

Full per-component coverage and every pin mapping are in [component-pin-audit.md](analysis/component-pin-audit.md). The reproducible audit is [check_design.py](analysis/helpers/check_design.py), with [raw_audit.json](analysis/2026-10-28_2128/raw_audit.json).

| Components | Manufacturer/source check | Result and remaining limitation |
|---|---|---|
| U1 CBM8051NST6 | Corebai PDF p. 3 pin diagram, pp. 4–8 ratings/electrical tables | Pins 1 OUT, 2 VSS, 3 IN+, 4 IN−, 5 disable control, 6 VDD match the board. Control is tied high; datasheet operating/disable thresholds support enabled operation. 5 V supply and ~2 V common mode are plausible. PCB metadata is stale. |
| U2 MS9280 | Ruimeng V1.3 PDF pp. 2–3, 6–8, 11–16 | All 28 pin functions checked. Top/bottom 2 V configuration and reference-capacitor topology match the intended mode. Physical reference routing is incomplete; clamp and capture timing remain open. Manufacturer document retrieved from a distributor mirror. |
| U3 LP5907MFX-3.3/NOPB | TI PDF p. 3 SOT-23 pin table, pp. 4–6 ratings | IN1, GND2, EN3, NC4, OUT5 match. EN tied to +5V, NC marked unconnected. C20/C21 provide nominal 1 µF input/output, with additional output bulk/bypass at U2. Check effective capacitance under bias, not only nominal value. |
| U4 HGSEMI LM1881M/TR | Exact C518922 document: pp. 1–3, 5, 14 | Pin functions and SOP-8 dimensions match. Pin 6 uses 680 kΩ and 100 nF; CVIN uses AC coupling and filtering. Supply minimum is a margin concern. |
| U5 SN74LVC3G17DCTR | TI PDF pp. 3–5 | Inputs 1/3/6, outputs 7/5/2, GND4, VCC8 match all four symbol units. Its 5.5 V input capability supports the LM1881-to-3.3 V translation. |
| D1/D2 PESD5V0S1BB | Nexperia PDF pp. 1–3, read via web | Bidirectional SOD523 device; no polarity-dependent reversal found. 35 pF typical / 45 pF maximum at the specified test point should be included in filter evaluation. A TVS rating alone does not demonstrate the downstream circuit survives a system ESD test. |
| J1/J4 AV-5 | Exact C18080 manufacturer drawing p. 1 | Board slots match: signal 2.2 × 1.0 mm at x=8.3; shell 1.5 × 2.5 mm at x=4.4, spacing 3.9 mm. Rotated drawing orientation agrees. The horizontal connector intentionally overhangs the board. Final fit/enclosure check still requires a physical sample. |
| J2 Tang Nano socket | Sipeed official pin diagram, raw footprint and CST | All 40 header positions compared, including reversed numbering direction on the right row. ADC D0–D9 mapping agrees with the FPGA pin constraints. Exact socket supplier drawing and module mechanical stack height were not independently obtained. |
| J3 expansion | Native netlist and raw footprint | 1×10, 2.54 mm header; functional map below. Exact supplier contact dimensions/current rating not independently checked. |
| R/C/L/FB, JP, TP, H | All raw values/footprints and pad assignments checked | Critical filter/divider/feedback values recomputed. Individual passive tolerance, MLCC bias curves, inductor Q/SRF, ferrite impedance and connector ratings were not exhaustively certified against exact-part PDFs. No polarized capacitor or discrete transistor ambiguity was found. |

The initial schematic analyzer issued DS-002 before datasheets were acquired. Subsequent manual checks above have explicit PDF evidence; the analyzer JSON itself still reflects its original limited datasheet coverage. No machine-readable extraction cache was produced. Do not interpret every automated electrical finding as datasheet-backed.

## Power tree and budget

```text
Tang Nano J2.40 +5V
  ├─ U3 LP5907, EN tied high → +3.3VA → U2 AVDD28 and MODE23
  │    input C20 1µF; output C21 1µF + C10 10µF / C9 100nF
  ├─ FB1 600Ω@100MHz → +5VA → U1 VDD6/control5, bias divider
  │    C7 10µF + C6 100nF
  └─ U4 LM1881 VCC8, C25 100nF
Tang Nano J2.19 / J2.25 +3V3
  ├─ U2 DRVDD2, C12 10µF + C11 100nF
  ├─ U5 VCC8, C26 100nF
  └─ J3.10 expansion supply
Common GND → all returns, both RCA shells and module ground pins
```

This is schematic intent; DR-01 prevents treating it as a working physical power tree.

U3 has ample nominal current rating for the ADC load, but the complete Tang Nano/USB and J3 external-load budget is unspecified. Using the ADC table’s 36.7 mA value gives roughly (5−3.3) × 0.0367 = **62.4 mW** regulator loss, before further margin and load details. J3’s permitted external current needs documenting. The 5 V rail has no carrier-level reverse-polarity or soft-start stage; its intended source is the module, not an arbitrary external supply.

The rails have nominal bulk and bypass capacitance. Startup sequencing, temporary drive into unpowered ADC inputs, and supply droop during module configuration require measurement. Do not forward the ADC clock before its analog supply is valid without checking the input-voltage limit. No measured inrush or USB source-impedance model was available.

## Analog and signal analysis

### Video filter and amplifier

The input is a shunt-C / series-L / shunt-C / series-L / shunt-C ladder: 220 pF, 3.3 µH, 680 pF, 3.3 µH, 220 pF. JP1 bridges the 75 Ω termination. C4 couples into the 10 kΩ bias network.

An ideal ABCD-network calculation with 75 Ω source and termination, including R2/C4 loading, gives:

| Frequency | Without diode capacitance | With 35 pF added at input |
|---|---:|---:|
| PAL chroma, 4.433619 MHz | −0.132 dB | −0.089 dB |
| 6 MHz | −2.886 dB | −2.701 dB |
| Nyquist, 13.5 MHz | −35.425 dB | −36.372 dB |

These are relative to the 1 kHz insertion gain, not absolute connector voltage gain. Results support the documented filter intent. They omit winding loss, Q/SRF, nonlinear diode capacitance, layout parasitics and component tolerances. JP1-open loop-through is a different termination condition and is not covered by these numbers.

R3/R4 = 15 kΩ / 10 kΩ produces **2.000 V** bias from 5 V. U1 gain about that bias is **1 + R5/R6 = 1.500**. C4/R2 produces an approximate **1.58 Hz** input high-pass pole. U1’s output isolation resistor is R7 = 22 Ω. Both the output load and feedback-loop layout should be checked on the prototype for ringing; no device-model transient simulation was performed.

### ADC reference, clamp and range

U2 MODE23 is on +3.3VA, REFSENSE18 and REFBS25 are grounded, and REFTS21 joins VREF26 in the schematic. C17/C18 decouple VREF; C15/C16 span REFTF–REFBF; C13/C14 return the reference nodes to GND. This matches the 2 V top/bottom topology shown in MS9280 Figure 4. The PCB lacks the completed VREF and REFBF connections listed above.

R8/R9 = 10 kΩ / 4.3 kΩ gives **CLAMPIN = 0.6014 V**. At gain 1.5 and nominal 1 Vpp video, approximate 8-bit-equivalent levels are sync tip **19.4**, blanking **77.0**, white **211.4**. This fits the 0–2 V span in the nominal case. Include input amplitude, clamp offset and gain tolerance in clipping tests.

The clamp control is active high. Its 40-cycle gate gives 1.481 µs; 54 cycles would be 2 µs at 27 MHz, but blindly extending the gate may intrude into active video. Model the ADC pipeline/detector latency and available back porch before changing the window. The 22 µs R7/C8 time constant implies multicycle acquisition for large initial offsets; it is not proof the circuit fails. Measure startup capture, blank-level settling, head-switch recovery and interline droop.

Calculations are reproducible with [check_analog.py](analysis/helpers/check_analog.py); results are in [analog-calculations.txt](analysis/2026-10-28_2128/analog-calculations.txt).

### Reference input and digital interface

JP2/R13 terminate REF IN at 75 Ω. R14/C22 = 620 Ω / 510 pF gives an approximate **503 kHz** sync-path low-pass pole; C23 is 100 nF AC coupling. This is consistent with the manufacturer’s sync-input filtering example. U4 RSET uses 680 kΩ with 100 nF filtering. U5 translates all three sync outputs into the 3.3 V domain, with series resistors toward the headers.

At 27 MHz, one period is **37.037 ns** and half a period is **18.519 ns**. The MS9280 table lists **25 ns typical** output delay, not a usable complete min/max timing guarantee. The nominal full-cycle difference is only 12.037 ns before clock-output, PCB, input and setup delays. `ADC_CLK_INVERT=1` changes which data transition is near the capture edge; it must be evaluated rather than assumed to improve capture. The existing CST supplies locations/electrical attributes; no external ADC timing constraint file was found.

## Connector reference

J2 numbering matches the official Sipeed diagram viewed with USB-C at the top: left row 1–20 downward; right row 21–40 upward. U2 D0 goes to FPGA55, D1 to FPGA85, D2–D9 to FPGA31/30/29/26/25/28/27/77. CLK is FPGA74, CLAMP FPGA73 and OTR FPGA75. This agrees with the repository CST. Shared LCD/module peripheral functions must remain unused while these pins serve the carrier.

| J3 pin | Function |
|---:|---|
| 1 | GND |
| 2 | FPGA76 |
| 3 | REF_VSYNC / FPGA42 |
| 4 | REF_CSYNC / FPGA41 |
| 5 | REF_ODD / FPGA48 |
| 6 | FPGA49 |
| 7 | FPGA86 |
| 8 | FPGA72 |
| 9 | FPGA71 |
| 10 | +3V3 |

The onboard USB-UART uses FPGA69; it is separate from J3. The full J2 mapping is retained in the pin-audit appendix.

## PCB, thermal and EMC

There are **332 track segments, all on F.Cu**, 118 vias, and a multilayer GND zone on F.Cu/In1.Cu/B.Cu. In2.Cu has no routed signal tracks or plane fill in the current file. Four copper layers are enabled even though the analyzer reports only three layers with copper use. The rectangular outline is 62 × 58 mm. Nominal copper is 35 µm; F.Cu–In1.Cu dielectric is 0.1 mm.

Minimum track width is 0.2 mm. Via drill is 0.3 mm and nominal annular ring 0.15 mm. Project minimums include 0.15 mm track/clearance, but the assigned default net class requires **0.2 mm clearance**, explaining why 0.15 mm at R28 fails. The coarse DFM analyzer’s zero violations is not a substitute for native DRC.

The ADC clock route is 18.639 mm after R11 plus 7.116 mm before it; both are on F.Cu without signal vias. Keep the series resistor toward the source, avoid unnecessary test-point stubs and preserve the nearby In1 ground reference. There are no carrier USB/HDMI differential pairs to sign off; those interfaces are on the module.

GND is one connected island in the analyzer’s saved-copper graph. The +3V3 graph is fragmented, consistent with the native open connections; this is an electrical connectivity problem, not merely an EMC score. The saved zone’s reported fill ratio above 1 is the sum of three filled layers divided by one outline area, not excess physical copper.

Thermal analysis ran, but modeled **only U3**, estimating 0.189 W and 72.2 °C at 25 °C ambient with generic assumptions. It is not a complete-board temperature prediction. Using 62.4 mW and TI’s SOT-23 θJA of 193.4 °C/W gives roughly **12.1 °C rise**, conditional on that load and comparable thermal conditions. U1 dissipation is modest at its nominal few-mA current, U4 is up to about 50 mW from its 5 V/10 mA table point, and U2 is around 0.1 W at the stated datasheet conditions. The FPGA/module and enclosure thermal behavior were not modeled. No exposed-pad package is used on this carrier.

EMC analysis ran with 32 findings, 25 of them heuristic; six categories produced coverage in the summary. Its score of 34/100 is **not accepted as a release criterion** because of incomplete routing, stale fills and the classification problems below. Prioritize ground continuity beneath the ADC clock/data, short reference loops, and low-inductance returns from both RCA TVS devices. Prototype checks should include clock harmonics near 27/54/81/108 MHz, near-field scans around ADC/header routing, video noise with module activity, and cable-connected immunity tests. No compliance claim is made.

## Fabrication outputs and assembly

Existing exports contain all layers expected by the job file plus PTH and NPTH drills. Drill accounting is consistent with the PCB: **118 vias, 54 component holes, four mounting holes**. The Edge.Cuts centerline is 62 × 58 mm; the job-file extent of 62.1 × 58.1 mm includes an output-geometry convention and is not proof the board size changed.

The export set exists alongside a board with stale fills and unfinished routing. It has not been released or replaced by this review. Regenerate Gerbers, drill files, BOM and CPL together only after the source passes the corrected checks. A ZIP file and complete layer list do not establish manufacture readiness.

AV-5 uses plated slots; preserve the oval drills through fabrication. U1 must carry consistent value/manufacturer metadata. The J2 module symbol represents two physical sockets; preserve the BOM’s intended socket quantity and assembly instructions. Fiducials can be on a panel if agreed with the assembler. TP1–TP5 provide useful analog/clock/clamp/ground access, but direct accessible supply test points would improve bring-up.

## False positives and reviewer overrides

| Analyzer flag | Review disposition |
|---|---|
| VIN_RAW/VIN_FILT “power rails without source” | Dismiss as power-name misclassification: these are the externally driven analog video path, not supply rails. |
| Three 5 V / 3.3 V domain-crossing errors at U4/U5 | Dismiss as missing device knowledge: U5 is the intended 5.5 V-tolerant input buffer powered at 3.3 V. |
| All three adjacent layer pairs are “signal layers” | Dismiss the automatic conclusion: KiCad layer type is `signal`, but every track is on F.Cu and In1 carries GND fill. Layer metadata alone does not establish an adjacent-signal-layer stackup. |
| C15/C16 “far from ground via” | Do not treat as missing ground bypass: these capacitors span the ADC reference nodes; assess their reference-current loop and C13/C14 ground paths. |
| J1/J4 courtyard outside board | Intentional horizontal RCA overhang supported by the exact AV-5 drawing. Keep enclosure clearance checks. |
| C5 “0.42 mm from edge” | No native copper-edge violation was reported. Treat as a mechanical placement advisory; do not elevate the coarse heuristic to a fabrication rule failure. |
| R27/R28 foreign GND zone | Real stale-fill collision in the saved board; clears on refill. Keep DR-02 until the source is saved/refabrication outputs regenerated. |
| Gerber alignment inferred from differing copper extents | Not evidence of shifted layers: In2 is largely pad copper and other layers have large pours. Exact registration was not independently reconstructed from all plots. |
| Paste-flash count vs total copper-flash count | Copper includes vias, through-hole pads and non-pasted features. The percentage alone does not establish missing paste. No complete aperture-by-aperture stencil audit was performed. |
| Fiducial detector mentions BGA/fine-pitch QFN | Carrier has neither; the smallest pad dimension triggered a generic label. Absence of fiducials remains a process discussion, not an automatic electrical blocker. |
| GP-001 sampled plane coverage | Retain as inspection leads, not proven plane splits. Saved fills are stale; endpoint/connector clearances and coarse sampling can bias percentages. Recheck actual ground beneath repaired routes after refill. |

## Previous review delta

No prior formal design-review Markdown or KiCad-happy manifest was present before this run. An older placement `review.json` refers to an intermediate `s1_full` board with resistor arrays and different routing; its `open_nets: []` is not evidence the current carrier is complete. No compatible previous analyzer run was available for `diff_analysis.py`. The README’s unrouted-board and Same Sky connector descriptions are stale relative to the current sources/BOM.

## Analysis coverage and limits

| Check | Status |
|---|---|
| `analyze_schematic.py` | Completed |
| `analyze_pcb.py --full --proximity` | Completed on saved board |
| `cross_analysis.py` | Completed |
| `analyze_emc.py` | Completed; heuristic risk review, no compliance certification |
| `analyze_thermal.py` | Completed; limited to one automatically modeled component |
| `analyze_gerbers.py` | Completed on existing exports |
| Native ERC / netlist | Completed; complete pin-net comparison performed |
| Native DRC / parity | Completed both before and after in-memory refill |
| SPICE | Not performed: ngspice, LTspice and Xyce were not found on PATH; standard macOS LTspice app path was absent. Ideal numerical network calculations supplement but do not replace device simulation. |
| Lifecycle audit | Attempted for 28 unique MPNs; all returned unknown. Available unauthenticated source does not provide authoritative lifecycle status; no obsolescence assurance. |
| Datasheet acquisition / review | Exact PDFs for U1–U5 and AV-5 obtained; diode PDF read via web; module official pin diagram checked. DigiKey sync lacked credentials; exact catalogue fallback succeeded. |
| Structured datasheet extraction | Not performed; manual page-specific evidence used. Analyzer JSON retains pre-download coverage warnings. |
| Deep review evidence gate | Four recorded findings accepted, zero quarantined. Gate checks citation/anchor integrity, not engineering completeness. |
| Physical measurements | Not performed: no powered hardware, oscilloscope capture, module fit, enclosure test or thermal/EMC measurements |
| Complete passive and connector qualification | Not performed; exact passive derating/Q/SRF and socket supplier drawing remain gaps |
| Full RTL/TBC functional review | Outside this hardware review; ADC clamp/capture and pin mapping inspected, no full video-processing sign-off |

The analyzer trust labels are mixed: schematic/thermal/Gerber mixed, EMC low, PCB/cross-analysis high but with 0% reported provenance coverage in those envelopes. These are tool self-labels, not an overall assurance rating. Highest-confidence blockers here come from native DRC and independent raw/netlist checks. Device correctness claims are limited to the explicitly cited manual datasheet checks.

## Recommended correction order

1. Complete supply and ADC reference routing, then all remaining signal branches; retain all 17 native DRC items as the closure checklist.
2. Fix R2/TP1 placement and R28/GND-via clearance; synchronize U1 metadata.
3. Refill and save zones, rerun native DRC/ERC/parity, and inspect actual ADC return paths.
4. Clean critical silkscreen and settle fiducial/panel and socket assembly requirements.
5. Resolve clamp/capture timing and low-supply behavior with a documented bring-up plan.
6. Generate a new coherent fabrication/assembly set from that corrected revision.

## Evidence files

- [Analyzer run](analysis/2026-10-28_2128/)
- [Deep-review record](analysis/deep_review.json)
- [Complete component and pin audit](analysis/component-pin-audit.md)
- [Datasheet manifest](datasheets/manifest.json)
- [Corebai CBM8051N PDF](datasheets/CBM8051NST6.pdf)
- [Ruimeng MS9280 PDF](datasheets/MS9280.pdf)
- [TI LP5907 PDF](datasheets/LP5907MFX-3.3_NOPB.pdf)
- [HGSEMI LM1881M/TR PDF](datasheets/LM1881M_TR.pdf)
- [TI SN74LVC3G17 PDF](datasheets/SN74LVC3G17DCTR.pdf)
- [BOOMELE AV-5 drawing](datasheets/AV-5.pdf)
- [Nexperia diode datasheet](https://assets.nexperia.com/documents/data-sheet/PESD5V0S1BB.pdf?335=)
- [Sipeed module documentation](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html)
