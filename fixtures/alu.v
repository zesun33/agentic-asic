// 8-bit Parameterized Synchronous Arithmetic Logic Unit
module alu (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [3:0]  op,
    input  wire [7:0]  a,
    input  wire [7:0]  b,
    output reg  [7:0]  out,
    output reg         zero
);

    reg [7:0] next_out;

    always @(*) begin
        case (op)
            4'b0000: next_out = a + b;           // ADD
            4'b0001: next_out = a - b;           // SUB
            4'b0010: next_out = a & b;           // AND
            4'b0011: next_out = a | b;           // OR
            4'b0100: next_out = a ^ b;           // XOR
            4'b0101: next_out = a << b[2:0];     // SLL
            4'b0110: next_out = a >> b[2:0];     // SRL
            4'b0111: next_out = (a < b) ? 8'd1 : 8'd0; // SLT
            default: next_out = 8'h00;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            out  <= 8'h00;
            zero <= 1'b1;
        end else begin
            out  <= next_out;
            zero <= (next_out == 8'h00);
        end
    end

endmodule
