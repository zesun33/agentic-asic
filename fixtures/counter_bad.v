// Malformed counter with blocking assignments in sequential block & unhandled latch
module counter_bad (
    input  wire clk,
    input  wire en,
    output reg [3:0] count
);

    // Flaw 1: Blocking '=' in clocked block
    // Flaw 2: Missing reset
    always @(posedge clk) begin
        if (en)
            count = count + 1;
    end

endmodule
