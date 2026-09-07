`timescale 1ns/1ps

module counter_assert_tb;
    reg clk;
    reg rst_n;
    wire [3:0] count;

    counter_assert dut (
        .clk(clk),
        .rst_n(rst_n),
        .count(count)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;

        #20;
        rst_n = 1;

        #50;
        if (count == 4'd0) begin
            $fatal(1, "FAIL: Counter did not increment!");
        end

        $display("PASS: counter_assert testbench completed successfully with count=%0d", count);
        $finish(0);
    end
endmodule
