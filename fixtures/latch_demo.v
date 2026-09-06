// Malformed combinational logic inferring transparent latches
module latch_demo (
    input  wire [1:0] sel,
    input  wire [7:0] a,
    output reg  [7:0] y
);

    // Intentional Latch: Missing 'else' or incomplete cases without default
    always @(*) begin
        if (sel == 2'b00)
            y = a;
        else if (sel == 2'b01)
            y = 8'hFF;
        // Missing sel == 2'b10 and 2'b11! Yosys MUST detect transparent latch!
    end

endmodule
