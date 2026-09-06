// 4-entry by 8-bit Synchronous FIFO
module fifo (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       wr_en,
    input  wire       rd_en,
    input  wire [7:0] wr_data,
    output reg  [7:0] rd_data,
    output wire       full,
    output wire       empty
);

    reg [7:0] mem [0:3];
    reg [1:0] wr_ptr;
    reg [1:0] rd_ptr;
    reg [2:0] count;

    assign full  = (count == 3'd4);
    assign empty = (count == 3'd0);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr  <= 2'b00;
            rd_ptr  <= 2'b00;
            count   <= 3'd0;
            rd_data <= 8'h00;
        end else begin
            case ({wr_en && !full, rd_en && !empty})
                2'b10: begin
                    mem[wr_ptr] <= wr_data;
                    wr_ptr      <= wr_ptr + 2'b01;
                    count       <= count + 3'd1;
                end
                2'b01: begin
                    rd_data <= mem[rd_ptr];
                    rd_ptr  <= rd_ptr + 2'b01;
                    count   <= count - 3'd1;
                end
                2'b11: begin
                    mem[wr_ptr] <= wr_data;
                    wr_ptr      <= wr_ptr + 2'b01;
                    rd_data     <= mem[rd_ptr];
                    rd_ptr      <= rd_ptr + 2'b01;
                end
                default: ;
            endcase
        end
    end

endmodule
