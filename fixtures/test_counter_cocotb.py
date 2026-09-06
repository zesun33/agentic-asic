import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_counter_reset_and_count(dut):
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    # Assert reset
    dut.rst_n.value = 0
    dut.en.value = 0
    await Timer(25, units="ns")
    assert dut.count.value == 0, f"Expected 0 after reset, got {dut.count.value}"

    # Deassert reset
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    assert dut.count.value == 0

    # Enable counter
    dut.en.value = 1
    for i in range(1, 5):
        await RisingEdge(dut.clk)
        assert dut.count.value == i, f"Cycle {i}: Expected {i}, got {dut.count.value}"
