create_clock -name clk -period 2.000 [get_ports clk]
set_input_delay  0.400 -clock clk [get_ports rst_n]
set_input_delay  0.400 -clock clk [get_ports en]
set_output_delay 0.400 -clock clk [get_ports count*]
