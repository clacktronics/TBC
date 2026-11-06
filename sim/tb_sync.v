// Feeds sim/vectors/cvbs.hex through sync_detect and logs every event in
// the same format as py/eval_sync.py --vectors (expected_events.txt).
`timescale 1ns/1ps
`include "vectors/n_samples.vh"
module tb_sync;
    reg clk = 1'b0;
    always #18.518 clk = ~clk;          // 27 MHz
    reg rst = 1'b1;
    reg [7:0] mem [0:`N_SAMPLES-1];
    reg [7:0] x = 8'd0;

    wire        ev_valid, fld_valid, fld_id, clamp, in_sync;
    wire [1:0]  ev_type;
    wire [39:0] ev_lead, ev_trail;
    wire [31:0] fld_k;
    wire [11:0] tip_q, blank_q;

    sync_detect dut (.clk(clk), .rst(rst), .ce(1'b1), .x(x),
        .ev_valid(ev_valid), .ev_type(ev_type), .ev_lead(ev_lead), .ev_trail(ev_trail),
        .fld_valid(fld_valid), .fld_id(fld_id), .fld_k(fld_k),
        .clamp(clamp), .in_sync(in_sync), .tip_q(tip_q), .blank_q(blank_q));

    integer fe, ff, i, nev = 0, nfld = 0;
    initial begin
        $readmemh("vectors/cvbs.hex", mem);
        fe = $fopen("out/rtl_events.txt", "w");
        ff = $fopen("out/rtl_fields.txt", "w");
        @(posedge clk); @(posedge clk);
        rst <= 1'b0;
        // the first sample must be presented on the first clock out of reset
        for (i = 0; i < `N_SAMPLES; i = i + 1) begin
            x <= mem[i];
            @(posedge clk);
        end
        repeat (40) @(posedge clk);
        $display("tb_sync: %0d samples, %0d events, %0d fields, tip=%0d.%0d blank=%0d.%0d",
                 `N_SAMPLES, nev, nfld, tip_q >> 4, tip_q[3:0], blank_q >> 4, blank_q[3:0]);
        $fclose(fe); $fclose(ff);
        $finish;
    end

    always @(posedge clk) begin
        if (ev_valid) begin
            $fwrite(fe, "E %0d %010x %010x\n", ev_type, ev_lead, ev_trail);
            nev = nev + 1;
        end
        if (fld_valid) begin
            $fwrite(ff, "F %0d %08x\n", fld_id, fld_k);
            nfld = nfld + 1;
        end
    end
endmodule
