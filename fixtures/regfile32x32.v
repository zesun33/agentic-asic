// 32x32-bit register file scale vehicle (1024 flops + decode + dual read).
// No asserts (formal auto-skips); async reset fully unrolled (review-clean).
module regfile32x32 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        we,
    input  wire [4:0]  waddr,
    input  wire [31:0] wdata,
    input  wire [4:0]  raddr_a,
    input  wire [4:0]  raddr_b,
    output reg  [31:0] rdata_a,
    output reg  [31:0] rdata_b
);

    reg [31:0] mem [0:31];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mem[0] <= 32'b0;
            mem[1] <= 32'b0;
            mem[2] <= 32'b0;
            mem[3] <= 32'b0;
            mem[4] <= 32'b0;
            mem[5] <= 32'b0;
            mem[6] <= 32'b0;
            mem[7] <= 32'b0;
            mem[8] <= 32'b0;
            mem[9] <= 32'b0;
            mem[10] <= 32'b0;
            mem[11] <= 32'b0;
            mem[12] <= 32'b0;
            mem[13] <= 32'b0;
            mem[14] <= 32'b0;
            mem[15] <= 32'b0;
            mem[16] <= 32'b0;
            mem[17] <= 32'b0;
            mem[18] <= 32'b0;
            mem[19] <= 32'b0;
            mem[20] <= 32'b0;
            mem[21] <= 32'b0;
            mem[22] <= 32'b0;
            mem[23] <= 32'b0;
            mem[24] <= 32'b0;
            mem[25] <= 32'b0;
            mem[26] <= 32'b0;
            mem[27] <= 32'b0;
            mem[28] <= 32'b0;
            mem[29] <= 32'b0;
            mem[30] <= 32'b0;
            mem[31] <= 32'b0;
        end else if (we) begin
            mem[waddr] <= wdata;
        end
    end

    always @(*) begin
        rdata_a = mem[raddr_a];
        rdata_b = mem[raddr_b];
    end

endmodule
