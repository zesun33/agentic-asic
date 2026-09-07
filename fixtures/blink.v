module blink (
    input  wire clk,
    output reg  led
);
    reg [23:0] div;
    always @(posedge clk) begin
        div <= div + 1'b1;
        led <= div[23];
    end
endmodule
