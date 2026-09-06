`timescale 1ns/1ps

module alu_tb;
    reg        clk;
    reg        rst_n;
    reg  [3:0] op;
    reg  [7:0] a;
    reg  [7:0] b;
    wire [7:0] out;
    wire       zero;

    alu dut (
        .clk(clk),
        .rst_n(rst_n),
        .op(op),
        .a(a),
        .b(b),
        .out(out),
        .zero(zero)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        op = 0;
        a = 0;
        b = 0;
        #15;
        rst_n = 1;
        #10;

        // Test ADD: 15 + 27 = 42
        op = 4'b0000; a = 8'd15; b = 8'd27;
        #10;
        if (out != 8'd42) begin
            $display("ERROR ADD: Expected 42, got %d", out);
            $fatal(1);
        end

        // Test SUB: 50 - 18 = 32
        op = 4'b0001; a = 8'd50; b = 8'd18;
        #10;
        if (out != 8'd32) begin
            $display("ERROR SUB: Expected 32, got %d", out);
            $fatal(1);
        end

        // Test XOR: 8'hF0 ^ 8'h0F = 8'hFF
        op = 4'b0100; a = 8'hF0; b = 8'h0F;
        #10;
        if (out != 8'hFF) begin
            $display("ERROR XOR: Expected FF, got %h", out);
            $fatal(1);
        end

        // Test ZERO flag: 8'd10 - 8'd10 = 0
        op = 4'b0001; a = 8'd10; b = 8'd10;
        #10;
        if (!zero) begin
            $display("ERROR ZERO: Expected zero flag = 1");
            $fatal(1);
        end

        $display("SUCCESS: All ALU assertions passed!");
        $finish;
    end
endmodule
