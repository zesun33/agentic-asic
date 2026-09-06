// 4-bit synchronous up-counter with active-low asynchronous reset
module counter (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       en,
    output reg  [3:0] count
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 4'b0000;
        end else if (en) begin
            count <= count + 4'b0001;
        end
    end

endmodule
