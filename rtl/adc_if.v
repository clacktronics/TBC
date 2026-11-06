// MS9280 / AD9280 interface: forwards the 27 MHz sample clock to the ADC and
// registers its parallel output.
//
// adc_d is the MS9280's 10-bit bus. An AD9280 fits the same footprint with
// its D7..D0 on adc_d[9:2]; adc_d[1:0] then read 0 (pulled down in the .cst).
//
// The ADC samples on its CLK rising edge and updates D after a
// pipeline delay plus an output delay (see its datasheet for tOD). Data is
// captured here on the FPGA's rising edge. If captures are noisy, set
// CLK_INVERT = 1 so the ADC is clocked half a period earlier relative to
// the capture edge, or add a capture-phase PLL later. A constant pipeline
// latency doesn't matter to the TBC.
`default_nettype none
module adc_if #(
    parameter CLK_INVERT = 0
) (
    input  wire       clk,
    input  wire [9:0] adc_d,
    input  wire       adc_otr,
    output wire       adc_clk,
    output reg  [9:0] x,
    output reg        otr
);
`ifdef SIM
    assign adc_clk = CLK_INVERT ? ~clk : clk;
`else
    // clock forwarding through an output DDR cell keeps the edge clean
    ODDR u_oddr (.CLK(clk), .D0(CLK_INVERT ? 1'b0 : 1'b1), .D1(CLK_INVERT ? 1'b1 : 1'b0),
                 .TX(1'b0), .Q0(adc_clk), .Q1());
`endif
    always @(posedge clk) begin
        x   <= adc_d;
        otr <= adc_otr;
    end
endmodule
`default_nettype wire
