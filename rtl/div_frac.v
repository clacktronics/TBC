// q = floor(256 * a / (a + b)) for a, b >= 0, a + b > 0.  Result 0..255.
// Restoring division, 8 iterations; 'done' pulses 9 clocks after 'start'.
// A new 'start' always restarts (cancels) a division in flight.
`default_nettype none
module div_frac (
    input  wire        clk,
    input  wire        rst,
    input  wire        start,
    input  wire [13:0] a,
    input  wire [13:0] b,
    output reg  [7:0]  q,
    output reg         done
);
    reg [15:0] r;
    reg [14:0] d;
    reg [3:0]  n;
    reg        busy;
    wire [15:0] r2 = {r[14:0], 1'b0};

    always @(posedge clk) begin
        done <= 1'b0;
        if (rst) begin
            busy <= 1'b0;
            q    <= 8'd0;
        end else if (start) begin
            r    <= {2'b00, a};          // a < a + b, so the integer part is 0
            d    <= {1'b0, a} + {1'b0, b};
            n    <= 4'd0;
            busy <= 1'b1;
        end else if (busy) begin
            if (r2 >= {1'b0, d}) begin
                r <= r2 - {1'b0, d};
                q <= {q[6:0], 1'b1};
            end else begin
                r <= r2;
                q <= {q[6:0], 1'b0};
            end
            n <= n + 4'd1;
            if (n == 4'd7) begin
                busy <= 1'b0;
                done <= 1'b1;
            end
        end
    end
endmodule
`default_nettype wire
