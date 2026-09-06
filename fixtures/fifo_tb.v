`timescale 1ns/1ps

module fifo_tb;
    reg        clk;
    reg        rst_n;
    reg        wr_en;
    reg        rd_en;
    reg  [7:0] wr_data;
    wire [7:0] rd_data;
    wire       full;
    wire       empty;

    fifo dut (
        .clk(clk),
        .rst_n(rst_n),
        .wr_en(wr_en),
        .rd_en(rd_en),
        .wr_data(wr_data),
        .rd_data(rd_data),
        .full(full),
        .empty(empty)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        wr_en = 0;
        rd_en = 0;
        wr_data = 0;
        #15;
        rst_n = 1;
        #10;

        if (!empty) begin
            $display("ERROR: FIFO should be empty initially");
            $fatal(1);
        end

        // Write 4 elements
        wr_en = 1; wr_data = 8'hAA; #10;
        wr_en = 1; wr_data = 8'hBB; #10;
        wr_en = 1; wr_data = 8'hCC; #10;
        wr_en = 1; wr_data = 8'hDD; #10;
        wr_en = 0;

        if (!full) begin
            $display("ERROR: FIFO should be full after 4 writes");
            $fatal(1);
        end

        // Read 1 element
        rd_en = 1; #10;
        rd_en = 0;
        if (rd_data != 8'hAA) begin
            $display("ERROR: Expected first read 0xAA, got 0x%h", rd_data);
            $fatal(1);
        end

        $display("SUCCESS: All FIFO assertions passed!");
        $finish;
    end
endmodule
