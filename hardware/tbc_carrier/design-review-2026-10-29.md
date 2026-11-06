# TBC carrier design review — 29 October 2026

**Verdict: the schematic is electrically plausible and the current PCB has no native electrical DRC errors. It is a credible prototype candidate, with the performance and supply-margin checks below still open. The existing fabrication outputs must not be used: they do not represent this board revision.**

Scope: current `tbc_carrier.kicad_sch`, `.kicad_pcb`, `.kicad_pro`, manufacturer datasheets, existing fabrication outputs, and the ADC-related RTL and pin constraints. Silkscreen violations are excluded as requested. No schematic, PCB, project-rule, or RTL changes were made.

## Findings requiring attention

| Priority | Finding | Action / evidence basis |
|---|---|---|
| Release blocker | **Existing Gerbers/drills are stale.** Their drill inventory has 118 vias; the current PCB has 130. | Regenerate the complete fabrication and assembly set together after any final edits. High confidence, raw PCB plus Gerber/drill analysis. |
| Warning | **U4 has no documented low-supply margin.** The fitted HGSEMI LM1881M/TR document specifies 5–12 V operation; its supply comes from nominal module/USB 5 V. | Establish the minimum voltage at U4 under cable and module load, or choose a device with an appropriate guaranteed supply range. High confidence in requirement; actual undervoltage is unmeasured. HGSEMI PDF p. 5. |
| Warning | **U3 output capacitance is nominally above its specified range.** C21 1 µF + C10 10 µF + C9 100 nF = **11.1 µF**, versus LP5907's 0.7–10 µF effective range. | Account for tolerance, temperature, DC bias and ESR. Reduce bulk capacitance or establish manufacturer-supported margin. This is not proof of oscillation: bias loss may bring the operating value below 10 µF. High-confidence calculation, TI PDF pp. 6, 15. |
| Validation required | **ADC clamp acquisition has not been established.** The gate is 40 clocks = **1.481 µs**, compared with the MS9280's **2 µs typical**, and R7 × C8 = **22 µs**. | Measure acquisition, line droop and recovery after disturbed sync; check gate placement against the actual video back porch. The 2 µs entry is not a specified minimum. Medium-confidence performance concern, MS9280 pp. 7, 15–16 and RTL. |
| Validation required | **ADC capture lacks a worst-case external timing budget.** The datasheet gives **25 ns typical** output delay, without a complete min/max guarantee. | Budget FPGA clock output delay, ADC delay, board delay and FPGA setup/hold; measure capture-phase margin. The current default is `ADC_CLK_INVERT=0`. High confidence that sign-off evidence is absent; no claim that capture necessarily fails. |
| Layout improvement | **Bottom-layer sync returns could be improved.** REF_CSYNC, REF_VSYNC and REF_ODD use B.Cu; adjacent In2.Cu contains routes but no ground plane. | Prefer routing over a ground reference and place GND stitching close to layer changes. Existing coplanar B.Cu ground and In1 ground provide returns; this is not an open circuit or a prediction of EMC failure. Medium-confidence engineering assessment. |
| Minor cleanup | **One VREF dangling track**, 0.3536 mm at approximately (144.25, 129.275) mm. | Remove the unused stub. Native DRC reports no disconnected VREF pads, so this is not yesterday's reference-open fault. High confidence. |
| Mechanical caution | **C5 is close to the left edge.** Courtyard clearance 0.425 mm; copper clearance **0.675 mm**; nominal body clearance about **0.775 mm**. | Move inward if convenient, particularly near panel breakout forces. It passes the configured 0.5 mm copper-edge rule. High-confidence geometry; stress risk depends on panel/assembly method. |

## Previous review delta

Compared with the 28 October review and its retained native DRC/netlist:

- **Fixed:** all 17 disconnected copper items, including supply and ADC reference connections.
- **Fixed:** copper-clearance, solder-mask-bridge and courtyard-overlap errors. An in-memory zone refill leaves the same clean electrical result.
- **Fixed:** U1 value mismatch. Current schematic and PCB values/footprints agree across all components, and native parity reports zero issues.
- **Changed:** 332 → 442 track segments; 118 → 130 vias. Routing now uses F.Cu, In2.Cu and B.Cu; In1.Cu remains ground-only.
- **Changed:** ADC/header assignment. The ten data bits now map to FPGA pins **52, 31, 30, 29, 26, 25, 28, 27, 77, 85** for D0–D9. The current CST agrees. Yesterday's mapping should not be reused.
- **Still open:** clamp acquisition, external capture timing, and U4 low-supply margin. Fiducial/panel strategy remains an assembly decision.
- **Newly highlighted:** total LP5907 output capacitance, bottom-layer sync return paths, C5 edge margin, and stale fabrication exports.

The PCB JSON delta is retained in `analysis/2026-10-29_review/pcb-diff.json`. The schematic analyzer reused the previous cache folder initially, so the schematic delta above is based on the retained **native netlist**, not an asserted pristine previous schematic JSON. Today's complete results are isolated in `analysis/2026-10-29_review/`.

## Native checks and verification basis

| Check | Saved board | In-memory refill |
|---|---:|---:|
| Electrical/copper clearance errors | 0 | 0 |
| Unconnected items | 0 | 0 |
| Schematic parity issues | 0 | 0 |
| Non-silkscreen warnings | 1: VREF stub | 1: VREF stub |

Native schematic ERC: **zero violations**. No DRC exclusions are configured. These results use the project's rules; they do not prove analog performance or EMC compliance. Refill was not saved to the source board.

The independent raw-file/native-netlist audit checked **all 236 net-assigned schematic pins against all 236 PCB pad assignments**, with **zero mismatches**. Analyzer connectivity partitions also match the native export. There are 79 unique physical components and 79 footprints; 82 non-power placed symbol units are expected because U5 is multi-unit.

Evidence: [pin audit](analysis/2026-10-29_review/component-pin-audit.md), [raw audit](analysis/2026-10-29_review/raw_audit.json), [saved DRC](analysis/2026-10-29_review/drc.json), [refilled DRC](analysis/2026-10-29_review/drc-refilled.json), [ERC](analysis/2026-10-29_review/erc.json).

## Component summary and datasheet checks

79 physical parts: 28 resistors, 26 capacitors, 5 ICs, 4 connectors, 2 inductors, 2 TVS diodes, 1 ferrite, 2 jumpers, 5 test points and 4 mounting holes. Every component's raw value, footprint and assigned pad nets is covered by the audit; passive pinout checks are generally not meaningful beyond connectivity and polarity. The datasheet checks below establish device correctness only for the stated facts.

| Part | Checks and conclusion | Source / confidence |
|---|---|---|
| U1 CBM8051NST6 | SOT-23-6 mapping OUT1, VSS2, IN+3, IN−4, control5, VDD6 agrees. Control high is consistent with enabled operation. 5 V supply, ~2 V input common mode and gain 1.5 are plausible. R7 isolates the output from the ADC coupling/load. | Corebai PDF p. 3 pin drawing, pp. 4–7 ratings/electrical tables, pp. 12–13 capacitive-load guidance. Datasheet-backed; stability still requires measurement. |
| U2 MS9280 | All 28 pin functions checked. AVDD28/MODE23 use +3.3VA; DRVDD2 uses +3V3; grounds1/14, THREE-STATE16, STBY17, REFSENSE18 and REFBS25 are grounded. VREF26 joins REFTS21. Reference capacitors match Figure 4. SSOP28 pitch 0.65 mm and 5.3 × 10.2 mm nominal body agree. | Ruimeng V1.3 PDF pp. 2–3, 5–8, 12, 15–20, 22. Manufacturer document retained locally from a mirror. |
| U3 LP5907MFX-3.3/NOPB | SOT-23 IN1/GND2/EN3/NC4/OUT5 correct; EN tied to input, NC unconnected. 5 V input and 3.3 V output are supported. Check combined capacitance as above. | TI PDF pp. 3–6, 15. Datasheet-backed. |
| U4 LM1881M/TR | Composite1, video input2, vertical3, GND4, back porch5, RSET6, odd/even7, VCC8 agree. Back-porch output intentionally unused. 680 kΩ RSET and 100 nF bypass/coupling are plausible. 620 Ω/510 pF input filter follows the example. | Exact HGSEMI PDF pp. 2–3, 5, 14; do not substitute TI supply guarantees for this manufacturer's part. |
| U5 SN74LVC3G17DCTR | All units checked: inputs1/3/6 → outputs7/5/2, GND4, VCC8. 3.3 V supply and 5 V sync inputs are supported by the 5.5 V input rating. SSOP DCT footprint matches. | TI PDF pp. 3–5. Datasheet-backed. |
| D1/D2 PESD5V0S1BB,115 | Bidirectional SOD523, so no polarity-dependent mounting error. The 35 pF typical/45 pF maximum capacitance is relevant to the video filter. Its clamp voltage is not a guarantee that downstream IC pins survive a system ESD event. | [Nexperia datasheet](https://assets.nexperia.com/documents/data-sheet/PESD5V0S1BB.pdf), pp. 1–4. |
| L1/L2 NLV25T-3R3J-EFD | 3.3 µH ±5%, Q ≥30 at 7.96 MHz, SRF ≥55 MHz, DCR ≤1.9 Ω. Frequency range is plausible for this filter; ideal-filter figures omit loss and self-capacitance. | [TDK product data](https://product.tdk.com/en/search/inductor/inductor/smd/info?part_no=NLV25T-3R3J-EFD). |
| J1/J4 AV-5 | Raw plated slots match drawing: signal 2.2 × 1.0 mm, shell 1.5 × 2.5 mm, spacing 3.9 mm. Overhang is intentional. | Local AV-5 PDF p. 1; drawing visually inspected. Actual connector fit remains unmeasured. |
| J2 module socket | 40 header positions checked against official module diagram; ADC mapping matches current constraints. D0 now uses FPGA52, also labelled HDMI EDID_DAT. Avoid simultaneous conflicting use of module peripherals. | [Sipeed documentation](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html), pin diagram, raw footprint and CST. Exact socket mechanical supplier drawing not obtained. |
| J3 expansion | 1×10 2.54 mm connector, ground pin1 and 3.3 V pin10; other pins match schematic/native netlist. | Internal consistency established; exact contact rating and mating hardware not independently qualified. |
| R/C/FB/JP/TP/H | All values and pad connections audited. Critical ratios and filter values recomputed. No discrete transistor pinout ambiguity or polarized-capacitor orientation issue. | Exact passive tolerances, aging, MLCC bias curves and ferrite characteristics not exhaustively qualified. |

The selected 1 µF CL10A105KB8NNNC is 50 V X5R ±10%, and 10 µF CL21A106KAYNNNE is 25 V X5R ±10%, with dimensions matching the chosen 0603/0805 packages. Voltage ratings have ample nominal margin; this does not eliminate capacitance derating. Sources: [Samsung 1 µF](https://product.samsungsem.com/mlcc/CL10A105KB8NNN.do), [Samsung 10 µF](https://product.samsungsem.com/mlcc/CL21A106KAYNNN.do). The X5R parts also limit any assumption of a whole-board 125°C operating rating.

## Power tree and thermal assessment

```text
J2.40 nominal +5V
  ├─ U3 LP5907 → +3.3VA → U2 AVDD/MODE
  │    CIN C20 1µF; COUT C21 1µF + C10 10µF + C9 100nF
  ├─ FB1 → +5VA → U1 and bias divider; C7 10µF + C6 100nF
  └─ U4 sync separator; C25 100nF
J2.19/J2.25 +3V3
  ├─ U2 digital output supply; C12 10µF + C11 100nF
  ├─ U5; C26 100nF
  └─ J3.10 expansion power
Common ground: carrier, module headers and RCA shells
```

At the MS9280's 36.7 mA table value, U3 dissipates approximately **(5−3.3)×0.0367 = 62.4 mW**. TI's SOT-23 θJA = 193.4°C/W gives approximately **12.1°C rise**, conditional on comparable thermal conditions. The automated thermal model instead assumes 0.189 W and predicts 72.2°C at 25°C ambient; it models only U3 and is not accepted as a measured whole-board result. U1's few-mA quiescent draw, U4's ≤10 mA at the specified 5 V test condition and U2's roughly 0.1 W do not suggest an obvious carrier hotspot. Module/enclosure heating remains unmodeled. No carrier IC uses an exposed thermal pad.

Minimum routed supply width is 0.2 mm; main +5V/+3V3 routes also use 0.33/0.66 mm. These are plausible for carrier loads of tens of mA. The permitted J3 load and total USB/module budget remain unspecified; no high-current expansion capability is established.

Check power-up with the actual module: U2 clock/input absolute limits are tied to AVDD, and +3V3 and +3.3VA are separately sourced. Firmware configuration delay probably helps normal startup, but that is not a guarantee for arbitrary rail sequencing or hot-plug. C20 must retain >0.7 µF at bias/temperature. C21+C10+C9 need a combined maximum-capacitance check as well as a minimum check. A nominal 10 µF bulk plus a nominal 1 µF local capacitor should not be treated as independent loads from the LDO's stability perspective.

## Analog plausibility and timing

The five-element input ladder is 220 pF / 3.3 µH / 680 pF / 3.3 µH / 220 pF with 75 Ω termination through bridged JP1. R3/R4 = 15 kΩ/10 kΩ gives 2.000 V bias; R5/R6 = 1 kΩ/2 kΩ gives gain 1.500 about that bias. The main input high-pass approximation is 1.58 Hz. The reference sync filter is approximately 503 kHz.

For a 75 Ω source and termination, including C4/R2 loading, the ideal ladder gives approximately **−0.13 dB at PAL chroma, −2.89 dB at 6 MHz and −35.43 dB at 13.5 MHz**, relative to 1 kHz insertion gain. Adding 35 pF at the input gives −0.09, −2.70 and −36.37 dB respectively. These results support the filter intent but omit winding loss, tolerances and full parasitics; JP1-open loop-through is a different network.

R8/R9 = 10 kΩ/4.3 kΩ sets CLAMPIN to **0.6014 V**. Nominal 1 Vpp video amplified by 1.5 gives ADC input levels approximately 0.151 V sync tip, 0.601 V blanking, 1.651 V white, fitting the 0–2 V reference span. Equivalent upper-eight-bit codes are about 19, 77 and 211. Clamp offset and source-amplitude variation must be included in clipping tests.

MS9280 pp. 15–16 explicitly trade input capacitance against acquisition and droop. R7=22 Ω exceeds the 10 Ω clamp-stability minimum. Although p. 17 recommends ≤20 Ω for the general wideband driver, it permits larger resistance for narrower-band applications; 22 Ω is not treated as a blocker for this ~6 MHz front end.

A simplified 1 V clamp correction to 10 mV needs **22 µs×ln(100) ≈101 µs cumulative clamp time**, around 68 pulses of the current width. This is an illustrative multicycle acquisition calculation, not a dynamic ADC simulation. Using 43 µA and 64 µs as example leakage/line-period values gives 2.75 mV droop on 1 µF; the current is not a worst-case guarantee. Test initial lock, sync disturbances, clipping, line tilt and noise. Do not blindly lengthen the pulse without allowing for ADC and detector latency and PAL/NTSC back-porch differences.

At 27 MHz, period = 37.037 ns and half-period = 18.519 ns. Subtracting 25 ns typical ADC output delay leaves 12.037 ns before FPGA/PCB/setup contributions for a full-cycle interpretation. The phase and valid data cycle must be established from the waveform. Pin constraints and an internal frequency target alone do not close this interface. `rtl/adc_if.v` samples on the rising edge and forwards the clock through ODDR; current `top.v` defaults to no inversion. No external input/output delay constraint file was found.

Calculations: [analog results](analysis/2026-10-29_review/analog-calculations.txt), [additional results](analysis/2026-10-29_review/detail-calculations.txt). Reproducible helpers are retained under `analysis/helpers/`.

## PCB and physical design

The closed rectangular outline is **62 × 58 mm**, four copper layers, nominal 1.6 mm thickness and 35 µm copper. Specified F.Cu–In1 and In2–B.Cu dielectric is 0.1 mm; this must match the eventual fabrication stackup. There are 390 F.Cu, 31 In2.Cu and 21 B.Cu segments, plus 130 vias. The GND zone spans F.Cu/In1.Cu/B.Cu. In1 has no signal tracks and is largely continuous; the filled-copper graph has one ground island.

Native plots were inspected for front copper, inner ground, inner routes, back copper and component bodies. The ADC clock remains on F.Cu with **7.116 mm before R11 and 18.639 mm after it**, without signal vias. ADC_AIN is 3.521 mm. Reference routes are all front-layer; VREF total copper length is 15.069 mm including branches and the small stub, REFTF 6.502 mm and REFBF 6.936 mm. U1's inverting node has 6.715 mm of total copper; keep this node compact and check high-frequency ringing on the prototype.

Supply bypass placement is generally compact: C6–U1 ~2.03 mm, C25–U4 ~2.33 mm, C26–U5 ~1.85 mm, U3 input/output caps ~1.83/2.06 mm by the analyzer's proximity metric. ADC supply/reference capacitors cluster around its analog and digital pins. These distances support plausibility but do not substitute for loop-inductance or impedance measurements.

RCA footprints intentionally overhang the left edge; this is appropriate for the connector direction. Their plated slots match the supplied drawing. J2 provides two socket rows with no obvious carrier body collision. Final socket height, module underside clearance, cable-plug access and enclosure mounting require a physical fit check. C5 is near the edge as quantified above; avoid placing a panel tab beside it.

Typical vias are 0.6 mm diameter / 0.3 mm drill, giving 0.15 mm nominal annular ring. Project limits include 0.15 mm global clearance, **0.2 mm default net-class clearance**, and 0.5 mm copper-edge clearance. Native DRC passes these checks. There is no mains or safety-isolation section; high-voltage creepage analysis is not applicable.

## EMC and cross-domain interpretation

EMC analysis completed with 35 findings, mostly heuristic. Its 31/100 score is **not a release or compliance criterion**. The cross-domain analyzer's +3V3 “two islands” report is not an actual native connectivity failure; native DRC and complete pad-net audit take precedence.

The meaningful layout concern is the new bottom sync routing. The closest standalone GND vias to the three sync layer changes are approximately 1.25 mm (CSYNC), 2.38 mm (ODD), and 3.26 mm (VSYNC); the U4 CSOUT inner-layer transitions are 2.04 and 2.21 mm from GND vias. Nearby ground pads/continuous copper also help, so these distances are not universal pass/fail thresholds. Adding close return stitching and using routes adjacent to a ground plane would improve margin.

The ADC clock's reported reference gap reduces to a sample at **(159.0,107.92) mm**, the J2 signal through-hole antipad. This is expected clearance at a pad, not evidence of a long plane split beneath the clock. The remaining bottom sync “coverage” percentages assess the empty adjacent In2 plane; they do not account fully for coplanar ground or the more distant In1 plane. Preserve the distinction between weaker return geometry and a missing return connection.

Prototype priorities: look for 27 MHz clock-related noise in captured video; inspect clock/data edges at the ADC/header; check sync outputs with cables attached; and assess ESD return behavior at the RCA inputs. No measured emissions or immunity claim is made.

## Manufacturing, false positives and limits

- The existing export set includes the expected copper/mask layers, outline, and PTH/NPTH drills, but **is stale**. Complete layer presence is not freshness. Regenerate Gerbers, drills, BOM and CPL as one revision; preserve AV-5 plated slots and the quantity of two physical sockets represented by J2.
- No board fiducials are present. Agree board or panel fiducials with the assembler. The analyzer's claim of a BGA/fine-pitch QFN is incorrect: this carrier has neither.
- Low automated test-point percentage is advisory. Existing pads expose useful analog/clock/clamp nodes; accessible supply/reference points would help bring-up.
- VIN_RAW/VIN_FILT “unsourced power rails” are video signal-name misclassification.
- Three U4/U5 domain-crossing errors are dismissed: the SN74LVC3G17 inputs are explicitly tolerant of the 5 V signals.
- Generic “adjacent signal layers” flags misread KiCad layer type declarations as actual copper usage. In1 is a ground plane.
- C5's 0.42 mm proximity flag is a courtyard measurement, not a native copper-clearance violation. RCA overhang is intentional.
- Gerber extent differences do not establish layer misregistration; trace-only inner layers naturally occupy different bounds. Paste flash count need not equal copper flash count because vias and through-hole pads do not all receive paste. These heuristic flags are not independent blockers.
- Multilayer zone fill ratio >1 sums several layers against one outline area; it does not mean copper extends outside the board.
- Silkscreen findings are excluded throughout this verdict.

## Analyses performed and remaining coverage gaps

| Analysis | Status |
|---|---|
| Schematic analyzer | Completed; raw/native connectivity cross-check completed for every assigned pin |
| PCB analyzer `--full --proximity` | Completed; native copper and component plots inspected |
| Cross-domain, EMC, thermal | All completed and triaged; thermal model covers only U3 |
| Gerber/drill analysis | Completed on existing outputs; stale revision identified |
| Native ERC, netlist, DRC, parity | Completed; DRC repeated with in-memory refill |
| Prior-review delta | Completed using prior report, PCB JSON and retained native netlist |
| Datasheet review | Manual page-specific checks for all five ICs and RCA drawing; diode, module and selected passives checked against manufacturer sources |
| Structured extraction cache | Not created; automated datasheet-aware checks remain less complete than manual review |
| Deep-review evidence gate | Eight findings accepted, zero quarantined; five marked partial because automated PDF text verification was unavailable. Manual evidence is identified above; the gate does not validate the engineering conclusion. |
| SPICE | Attempted; no ngspice, LTspice or Xyce available. Analytical calculations completed; no device-model stability/transient simulation |
| Lifecycle | Audit attempted for 28 MPNs; all unknown from the available source. Selected manufacturer pages show production status, but no complete lifecycle assurance |
| Bench / mechanics | No powered-board tests, oscilloscope measurements, thermal/EMC tests, enclosure model or physical mating trial |
| Passive qualification | No complete MLCC bias/temperature/aging envelope, tolerance Monte Carlo, full S-parameter model or exact connector contact-current qualification |
| Firmware | ADC mapping, clock/capture and clamp logic examined; full TBC/video-processing correctness is outside this review |

Trust summary: high confidence in source connectivity, native DRC and stated datasheet pin/rating checks; medium confidence in unmeasured analog/layout performance judgments; no hardware-validation or compliance confidence claimed. The automated trust labels are not a substitute for these distinctions.

**Recommended next steps:** resolve or explicitly accept the U4 supply and U3 capacitance margins; remove the VREF stub and consider return stitching/C5 edge margin; regenerate manufacturing outputs; then validate ADC capture and clamp behavior on the prototype. No confirmed pinout or electrically open/shorted-board blocker remains in the current source files.
