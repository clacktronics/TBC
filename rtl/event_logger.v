// Streams sync measurements to the host over UART for first-light testing.
//
// Packet (10 bytes, big-endian):
//   0xA5, flags, lead[31:0], trail[31:0]
//   flags = {field_marker, field_id, 4'b0, type[1:0]}
//   lead/trail are the low 32 bits of the 32.8 timestamps (24.8: wraps
//   every ~0.62 s, which the host unwraps).
//
// Sent: a field marker for the first broad pulse of every field, and one
// hsync in every DECIM, counted from the start of the field so the same
// line numbers are reported every field. Defaults fit 115200 baud.
`default_nettype none
module event_logger #(
    parameter integer DECIM        = 32,
    parameter integer CLKS_PER_BIT = 234
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        ev_valid,
    input  wire [1:0]  ev_type,
    input  wire [39:0] ev_lead,
    input  wire [39:0] ev_trail,
    input  wire        fld_valid,
    input  wire        fld_id,
    output wire        tx,
    output reg         overflow
);
    // ---- event selection ----
    reg [15:0] hcount;
    reg        push;
    reg [71:0] push_data;

    always @(posedge clk) begin
        push <= 1'b0;
        if (rst) begin
            hcount <= 16'd0;
        end else begin
            if (ev_valid) begin
                if (ev_type == 2'd1) begin
                    if (hcount == 16'd0) begin
                        push <= 1'b1;
                        push_data <= {8'h01, ev_lead[31:0], ev_trail[31:0]};
                    end
                    hcount <= (hcount == DECIM - 1) ? 16'd0 : hcount + 16'd1;
                end
            end
            if (fld_valid) begin     // same clock as the broad pulse's event
                hcount <= 16'd0;
                push <= 1'b1;
                push_data <= {1'b1, fld_id, 6'h02, ev_lead[31:0], ev_trail[31:0]};
            end
        end
    end

    // ---- 16-entry FIFO ----
    reg [71:0] fifo [0:15];
    reg [4:0]  wr, rd;
    wire       empty = (wr == rd);
    wire       full  = (wr[3:0] == rd[3:0]) && (wr[4] != rd[4]);

    // ---- serialiser ----
    reg  [71:0] pkt;
    reg  [3:0]  idx;
    reg         sending;
    wire        u_ready;
    reg         u_valid;
    reg  [7:0]  u_data;
    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_tx (.clk(clk), .rst(rst),
        .valid(u_valid), .data(u_data), .ready(u_ready), .tx(tx));

    always @(posedge clk) begin
        u_valid <= 1'b0;
        if (rst) begin
            wr <= 5'd0; rd <= 5'd0; sending <= 1'b0; overflow <= 1'b0;
        end else begin
            if (push) begin
                if (!full) begin
                    fifo[wr[3:0]] <= push_data;
                    wr <= wr + 5'd1;
                end else begin
                    overflow <= 1'b1;
                end
            end
            if (!sending) begin
                if (!empty) begin
                    pkt <= fifo[rd[3:0]];
                    rd <= rd + 5'd1;
                    sending <= 1'b1;
                    idx <= 4'd0;
                end
            end else if (u_ready && !u_valid) begin
                u_valid <= 1'b1;
                if (idx == 4'd0) begin
                    u_data <= 8'hA5;
                end else begin
                    u_data <= pkt[71:64];
                    pkt <= {pkt[63:0], 8'h00};
                end
                idx <= idx + 4'd1;
                if (idx == 4'd9) sending <= 1'b0;
            end
        end
    end
endmodule
`default_nettype wire
