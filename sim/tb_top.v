// Whole-design test: ADC samples in at the pins, UART packets out.
// Uses a fast UART (8 clocks/bit) and DECIM=4 so a short run carries data.
`timescale 1ns/1ps
`include "vectors/n_samples.vh"
module tb_top;
    localparam CPB = 8;
    reg clk = 1'b0;
    always #18.518 clk = ~clk;
    reg [7:0] mem [0:`N_SAMPLES-1];
    reg [7:0] adc_d = 8'd76;
    wire adc_clk, adc_clamp, tx;
    wire [5:0] led;

    top #(.DECIM(4), .CLKS_PER_BIT(CPB)) dut (.clk27(clk), .btn_rst(1'b0),
        .adc_d({adc_d, 2'b00}), .adc_otr(1'b0), .adc_clk(adc_clk), .adc_clamp(adc_clamp),
        .uart_tx(tx), .led(led));

    integer i, fp, nbytes = 0, nclamp = 0;
    initial begin
        $readmemh("vectors/cvbs.hex", mem);
        fp = $fopen("out/rtl_uart.txt", "w");
        // present sample 0 so that sync_detect sees it on its first
        // clock out of reset (adc_if adds one register stage)
        // (stimulus changes on the falling edge to avoid races)
        @(negedge clk);
        while (dut.por != 16'h7FFF) @(negedge clk);
        for (i = 0; i < `N_SAMPLES; i = i + 1) begin
            adc_d = mem[i];
            @(negedge clk);
            if (adc_clamp) nclamp = nclamp + 1;
        end
        repeat (20000) @(posedge clk);
        $display("tb_top: %0d UART bytes, clamp high for %0d samples, leds=%b",
                 nbytes, nclamp, led);
        $fclose(fp);
        $finish;
    end

    // UART receiver
    integer k;
    reg [7:0] b;
    always begin
        @(negedge tx);
        repeat (CPB / 2) @(posedge clk);
        for (k = 0; k < 8; k = k + 1) begin
            repeat (CPB) @(posedge clk);
            b[k] = tx;
        end
        repeat (CPB) @(posedge clk);         // stop bit
        $fwrite(fp, "%02x\n", b);
        nbytes = nbytes + 1;
    end
endmodule
