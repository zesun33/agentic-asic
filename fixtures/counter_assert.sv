// Counter with an embedded assertion that holds by construction.
// Used by formal-stage integration tests (BMC proves count < 16).
module counter_assert (
    input  wire       clk,
    input  wire       rst_n,
    output reg  [3:0] count
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            count <= 4'b0000;
        else
            count <= count + 4'b0001;
    end

    // Guarded for iverilog (no SVA support): proven with -DFORMAL.
`ifdef FORMAL
    always @(posedge clk)
        assert (count < 5'd16);
`endif

endmodule
