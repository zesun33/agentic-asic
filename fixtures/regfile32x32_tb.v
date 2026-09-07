`timescale 1ns/1ps

module regfile32x32_tb;
    reg         clk;
    reg         rst_n;
    reg         we;
    reg  [4:0]  waddr;
    reg  [31:0] wdata;
    reg  [4:0]  raddr_a;
    reg  [4:0]  raddr_b;
    wire [31:0] rdata_a;
    wire [31:0] rdata_b;

    integer i;

    regfile32x32 dut (
        .clk(clk),
        .rst_n(rst_n),
        .we(we),
        .waddr(waddr),
        .wdata(wdata),
        .raddr_a(raddr_a),
        .raddr_b(raddr_b),
        .rdata_a(rdata_a),
        .rdata_b(rdata_b)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        we = 0;
        waddr = 5'd0;
        wdata = 32'd0;
        raddr_a = 5'd0;
        raddr_b = 5'd0;

        #20;
        rst_n = 1;

        for (i = 0; i < 8; i = i + 1) begin
            @(negedge clk);
            we = 1;
            waddr = i[4:0];
            wdata = 32'hA5A50000 + i;
        end
        @(negedge clk);
        we = 0;

        for (i = 0; i < 8; i = i + 1) begin
            raddr_a = i[4:0];
            raddr_b = 5'd7 - i[4:0];
            #1;
            if (rdata_a !== (32'hA5A50000 + i))
                $fatal(1, "rdata_a mismatch at %0d: got %h", i, rdata_a);
            if (rdata_b !== (32'hA5A50000 + (7 - i)))
                $fatal(1, "rdata_b mismatch at %0d: got %h", i, rdata_b);
        end

        $display("PASS: regfile32x32 dual-port readback of 8 locations");
        $finish(0);
    end
endmodule
