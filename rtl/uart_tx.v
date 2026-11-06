// 8N1 UART transmitter.
`default_nettype none
module uart_tx #(
    parameter integer CLKS_PER_BIT = 234      // 27 MHz / 115200
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       valid,
    input  wire [7:0] data,
    output wire       ready,
    output reg        tx
);
    reg [15:0] cnt;
    reg [3:0]  bitn;
    reg [9:0]  sh;
    reg        busy;
    assign ready = !busy;

    always @(posedge clk) begin
        if (rst) begin
            tx <= 1'b1; busy <= 1'b0; cnt <= 16'd0; bitn <= 4'd0;
        end else if (!busy) begin
            if (valid) begin
                sh   <= {1'b1, data, 1'b0};
                busy <= 1'b1;
                cnt  <= 16'd0;
                bitn <= 4'd0;
            end
        end else begin
            tx <= sh[0];
            if (cnt == CLKS_PER_BIT - 1) begin
                cnt <= 16'd0;
                sh  <= {1'b1, sh[9:1]};
                bitn <= bitn + 4'd1;
                if (bitn == 4'd9) busy <= 1'b0;
            end else begin
                cnt <= cnt + 16'd1;
            end
        end
    end
endmodule
`default_nettype wire
