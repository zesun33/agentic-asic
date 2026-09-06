`timescale 1ns/1ps

module counter_tb;
    reg clk;
    reg rst_n;
    reg en;
    wire [3:0] count;

    counter dut (
        .clk(clk),
        .rst_n(rst_n),
        .en(en),
        .count(count)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        en = 0;
        #15;
        rst_n = 1;
        #10;
        en = 1;
        #40;
        if (count != 4'd4) begin
            $display("ERROR: Expected count=4, got %d", count);
            $fatal(1);
        end
        $display("SUCCESS: Counter reached %d as expected", count);
        $finish;
    end
endmodule
