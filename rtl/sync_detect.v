// Composite sync detector with sub-sample edge timing.
//
// Bit-exact with py/sync_model.py - read that file for the algorithm.
// In short: [1 2 1] smoothing, self-calibrating 50% slicer with hysteresis,
// linear interpolation of the 50% crossing (8-bit fraction), pulse-width
// classification, sync-tip / back-porch level tracking, clamp gate and
// field (odd/even) detection.
//
// Timestamps are 32.8 fixed point in units of input samples, counted by a
// free-running counter that starts at -1 for the first sample after reset.
`default_nettype none
module sync_detect #(
    parameter [7:0] TIP0   = 8'd16,    // initial sync tip code
    parameter [7:0] BLANK0 = 8'd76     // initial blanking code
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        ce,          // one input sample per ce
    input  wire [7:0]  x,

    output reg         ev_valid,    // one pulse per sync pulse
    output reg  [1:0]  ev_type,     // 0 eq, 1 hsync, 2 broad, 3 invalid width
    output reg  [39:0] ev_lead,     // 50% leading (falling) edge, 32.8
    output reg  [39:0] ev_trail,    // 50% trailing (rising) edge, 32.8

    output reg         fld_valid,   // start of vertical sync (same clock as
                                    // that broad pulse's ev_valid)
    output reg         fld_id,      // 0 = field 1 (odd), 1 = field 2 (even)
    output reg  [31:0] fld_k,       // integer leading edge of first broad pulse

    output reg         clamp,       // back-porch gate (AD9280 CLAMP)
    output wire        in_sync,     // slicer state
    output reg  [11:0] tip_q,       // tracked levels, 8.4 fixed point
    output reg  [11:0] blank_q
);
    localparam signed [14:0] HYS_A = 15'sd96;
    localparam [9:0] GLITCH = 10'd27, EQ_MAX = 10'd80, HS_MAX = 10'd200,
                     BAD_MAX = 10'd400, LOWCNT_MAX = 10'd1023;
    localparam [9:0] TIP_OFS = 10'd24;
    localparam [7:0] BP_OFS = 8'd100, CLAMP_ON = 8'd96, CLAMP_OFF = 8'd136;
    localparam [3:0] BUSY = 4'd12;
    localparam [31:0] FIELD2_DELTA = 32'd5616;
    localparam [1:0] T_EQ = 2'd0, T_HS = 2'd1, T_BROAD = 2'd2, T_BAD = 2'd3;

    // ---------------- smoothing + slicing distance ----------------------
    reg  [7:0]  x1, x2;
    reg  [31:0] m;                                   // index being processed
    wire [9:0]  s4 = {2'b00, x2} + {1'b0, x1, 1'b0} + {2'b00, x};
    wire [12:0] lvl_sum = {1'b0, tip_q} + {1'b0, blank_q};
    wire signed [14:0] A = $signed({2'b00, s4, 3'b000}) - $signed({2'b00, lvl_sum});
    reg  signed [14:0] a_prev;

    // latest crossings (registered), and this sample's crossing (bypass)
    reg  [31:0] fall_m, rise_m;
    reg  signed [14:0] fall_a, fall_b, rise_a, rise_b;
    wire fall_now = (a_prev >= 0) && (A < 0);
    wire rise_now = (a_prev <= 0) && (A > 0);
    wire [31:0] fm = fall_now ? m : fall_m;
    wire signed [14:0] fa = fall_now ? a_prev : fall_a;
    wire signed [14:0] fb = fall_now ? A      : fall_b;
    wire [31:0] rm = rise_now ? m : rise_m;
    wire signed [14:0] ra = rise_now ? a_prev : rise_a;
    wire signed [14:0] rb = rise_now ? A      : rise_b;

    function [13:0] mag(input signed [14:0] v);
        mag = v[14] ? -v : v;
    endfunction

    // ---------------- divider (shared by both edges) ---------------------
    reg         div_start;
    reg  [13:0] div_a, div_b;
    wire [7:0]  div_q;
    wire        div_done;
    div_frac u_div (.clk(clk), .rst(rst), .start(div_start), .a(div_a), .b(div_b),
                    .q(div_q), .done(div_done));
    reg         div_is_trail;

    // ---------------- pulse state ---------------------------------------
    reg         low;
    reg  [9:0]  lowcnt;
    reg  [3:0]  busy;
    reg  [31:0] lead_int, trail_int;
    reg  [7:0]  lead_frac;
    reg  [1:0]  typ;
    reg  [14:0] tip_acc;
    reg         bp_active;
    reg  [7:0]  bp_cnt;
    reg  [14:0] bp_acc;
    assign in_sync = low;

    wire [3:0]  busy_now = (busy != 0) ? busy - 4'd1 : 4'd0;
    wire [9:0]  lc       = (lowcnt < LOWCNT_MAX) ? lowcnt + 10'd1 : lowcnt;
    wire        tip_win  = (lc >= TIP_OFS) && (lc < TIP_OFS + 10'd32);
    wire [14:0] tip_acc_now = tip_acc + (tip_win ? {5'd0, s4} : 15'd0);
    wire [7:0]  bc       = bp_cnt + 8'd1;
    wire        bp_win   = (bc >= BP_OFS) && (bc < BP_OFS + 8'd32);
    wire [14:0] bp_acc_now = bp_acc + (bp_win ? {5'd0, s4} : 15'd0);

    // IIR level updates: lvl += ((acc >> 3) - lvl) >>> 3
    wire signed [13:0] tip_err   = $signed({2'b00, tip_acc_now[14:3]}) - $signed({2'b00, tip_q});
    wire signed [13:0] blank_err = $signed({2'b00, bp_acc_now[14:3]})  - $signed({2'b00, blank_q});
    wire [11:0] tip_next   = tip_q   + {tip_err[13],   tip_err[13:3]};
    wire [11:0] blank_next = blank_q + {blank_err[13], blank_err[13:3]};

    wire [1:0] typ_now = (lc < EQ_MAX) ? T_EQ : (lc < HS_MAX) ? T_HS :
                         (lc < BAD_MAX) ? T_BAD : T_BROAD;

    always @(posedge clk) begin
        div_start <= 1'b0;
        if (rst) begin
            x1 <= 8'd0; x2 <= 8'd0; m <= 32'hFFFF_FFFF;
            a_prev <= 15'sd0;
            fall_m <= 32'd0; fall_a <= 15'sd0; fall_b <= 15'sd1;
            rise_m <= 32'd0; rise_a <= 15'sd0; rise_b <= 15'sd1;
            tip_q <= {TIP0, 4'd0}; blank_q <= {BLANK0, 4'd0};
            low <= 1'b0; lowcnt <= 10'd0; busy <= 4'd0;
            lead_int <= 32'd0; lead_frac <= 8'd0; trail_int <= 32'd0; typ <= 2'd0;
            tip_acc <= 15'd0; bp_active <= 1'b0; bp_cnt <= 8'd0; bp_acc <= 15'd0;
            clamp <= 1'b0; div_is_trail <= 1'b0;
        end else if (ce) begin
            x2 <= x1; x1 <= x;
            m <= m + 32'd1;
            a_prev <= A;
            if (fall_now) begin fall_m <= m; fall_a <= a_prev; fall_b <= A; end
            if (rise_now) begin rise_m <= m; rise_a <= a_prev; rise_b <= A; end
            busy <= busy_now;

            // back porch window / clamp gate
            if (bp_active) begin
                bp_cnt <= bc;
                bp_acc <= bp_acc_now;
                if (bc == BP_OFS + 8'd31) blank_q <= blank_next;
                clamp <= (bc >= CLAMP_ON) && (bc < CLAMP_OFF);
                if (bc >= CLAMP_OFF) bp_active <= 1'b0;
            end else begin
                clamp <= 1'b0;
            end

            // slicer (assignments below override the back-porch block)
            if (!low) begin
                if ((A <= -HYS_A) && (busy_now == 4'd0)) begin
                    low       <= 1'b1;
                    lowcnt    <= 10'd0;
                    lead_int  <= fm - 32'd1;
                    div_a     <= mag(fa);
                    div_b     <= mag(fb);
                    div_start <= 1'b1;
                    div_is_trail <= 1'b0;
                    tip_acc   <= 15'd0;
                    bp_active <= 1'b0;
                end
            end else begin
                lowcnt  <= lc;
                tip_acc <= tip_acc_now;
                if (A >= HYS_A) begin
                    low <= 1'b0;
                    if (lc >= GLITCH) begin
                        typ       <= typ_now;
                        trail_int <= rm - 32'd1;
                        div_a     <= mag(ra);
                        div_b     <= mag(rb);
                        div_start <= 1'b1;
                        div_is_trail <= 1'b1;
                        busy      <= BUSY;
                        if (typ_now == T_HS) begin
                            tip_q     <= tip_next;
                            bp_active <= 1'b1;
                            bp_cnt    <= 8'd0;
                            bp_acc    <= 15'd0;
                        end
                    end
                end
            end
        end
        // lead fraction is latched as soon as its division finishes
        if (!rst && div_done && !div_is_trail) lead_frac <= div_q;
    end

    // ---------------- event output + field detect -----------------------
    reg [31:0] last_h;
    reg        seen_broad;
    wire [39:0] lead_fx  = {lead_int, 8'd0}  + {32'd0, lead_frac};
    wire [39:0] trail_fx = {trail_int, 8'd0} + {32'd0, div_q};

    always @(posedge clk) begin
        ev_valid  <= 1'b0;
        fld_valid <= 1'b0;
        if (rst) begin
            last_h <= 32'd0; seen_broad <= 1'b1;
            ev_type <= 2'd0; ev_lead <= 40'd0; ev_trail <= 40'd0;
            fld_id <= 1'b0; fld_k <= 32'd0;
        end else if (div_done && div_is_trail) begin
            ev_valid <= 1'b1;
            ev_type  <= typ;
            ev_lead  <= lead_fx;
            ev_trail <= trail_fx;
            if (typ == T_HS) begin
                last_h     <= lead_int;
                seen_broad <= 1'b0;
            end else if (typ == T_BROAD && !seen_broad) begin
                seen_broad <= 1'b1;
                fld_valid  <= 1'b1;
                fld_id     <= ((lead_int - last_h) > FIELD2_DELTA);
                fld_k      <= lead_int;
            end
        end
    end
endmodule
`default_nettype wire
