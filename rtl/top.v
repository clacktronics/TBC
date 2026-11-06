// Tang Nano 20K top level - stage 1: ADC capture + sync measurement.
//
// MS9280 (10 bit) or AD9280 (8 bit, on adc_d[9:2]) on the header, clocked at
// the board's 27 MHz (1728 samples/line). Sync detection uses the top 8 bits.
// Sync edge timestamps stream out of the onboard USB-UART for plotting.
//
// LEDs (active low): 0 = sync present, 1 = 1 Hz field-rate blink,
//                    2 = ADC clipping (OTR) seen, 3 = field id,
//                    4 = UART FIFO overflowed, 5 = in sync pulse.
`default_nettype none
module top #(
    parameter integer DECIM        = 32,
    parameter integer CLKS_PER_BIT = 234,
    parameter         ADC_CLK_INVERT = 0
) (
    input  wire       clk27,
    input  wire       btn_rst,      // S1, active high
    input  wire [9:0] adc_d,
    input  wire       adc_otr,
    output wire       adc_clk,
    output wire       adc_clamp,
    output wire       uart_tx,
    output wire [5:0] led
);
    // power-on reset
    reg [15:0] por = 16'd0;
    wire rst = !por[15] || btn_rst;
    always @(posedge clk27) if (!por[15]) por <= por + 16'd1;

    wire [9:0] x10;
    wire       otr;
    adc_if #(.CLK_INVERT(ADC_CLK_INVERT)) u_adc (.clk(clk27), .adc_d(adc_d),
        .adc_otr(adc_otr), .adc_clk(adc_clk), .x(x10), .otr(otr));
    wire [7:0] x = x10[9:2];

    wire        ev_valid, fld_valid, fld_id, clamp, in_sync;
    wire [1:0]  ev_type;
    wire [39:0] ev_lead, ev_trail;
    wire [31:0] fld_k;
    wire [11:0] tip_q, blank_q;
    sync_detect u_sync (.clk(clk27), .rst(rst), .ce(1'b1), .x(x),
        .ev_valid(ev_valid), .ev_type(ev_type), .ev_lead(ev_lead), .ev_trail(ev_trail),
        .fld_valid(fld_valid), .fld_id(fld_id), .fld_k(fld_k),
        .clamp(clamp), .in_sync(in_sync), .tip_q(tip_q), .blank_q(blank_q));
    assign adc_clamp = clamp;

    wire overflow;
    event_logger #(.DECIM(DECIM), .CLKS_PER_BIT(CLKS_PER_BIT)) u_log (
        .clk(clk27), .rst(rst), .ev_valid(ev_valid), .ev_type(ev_type),
        .ev_lead(ev_lead), .ev_trail(ev_trail), .fld_valid(fld_valid),
        .fld_id(fld_id), .tx(uart_tx), .overflow(overflow));

    // status
    reg [19:0] since_h = 20'hFFFFF;        // ~39 ms to time out
    reg [4:0]  fcount = 5'd0;
    reg        blink = 1'b0, fid = 1'b0;
    reg [21:0] otr_hold = 22'd0;
    always @(posedge clk27) begin
        if (ev_valid && ev_type == 2'd1) since_h <= 20'd0;
        else if (since_h != 20'hFFFFF) since_h <= since_h + 20'd1;
        if (fld_valid) begin
            fid <= fld_id;
            fcount <= (fcount == 5'd24) ? 5'd0 : fcount + 5'd1;
            if (fcount == 5'd24) blink <= ~blink;
        end
        if (otr) otr_hold <= 22'h3FFFFF;
        else if (otr_hold != 0) otr_hold <= otr_hold - 22'd1;
    end
    assign led = ~{in_sync, overflow, fid, (otr_hold != 0), blink, (since_h != 20'hFFFFF)};
endmodule
`default_nettype wire
