// Counter with an embedded assertion that FAILS by construction.
// Used by formal-stage red-path integration tests (BMC refutes count != 0).
module counter_assert_bad (
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

    // Guarded for iverilog (no SVA support): refuted with -DFORMAL.
`ifdef FORMAL
    always @(posedge clk)
        assert (count != 4'b0000);
`endif

endmodule
