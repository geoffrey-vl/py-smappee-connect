"""
Smappee Infinity – Bus Info reader

Reads the Bus Info block for each of the 10 possible bus devices (FC3).

Bus Info register map (from XLS):
  Device 0 base: 5248  (+32 per device)
  Offset +0  : Device Type       (Int16)
  Offset +1  : Assigned slots    (Int16)
  Offset +2-3: Serial number     (Int32)
  Offset +4  : FW minor version  (Int16)
  Offset +5  : FW major version  (Int16)
  Offset +6-7: Status word       (Int32)
  Offset +8-9: Last reading      (Int32)
"""

import argparse

from pymodbus import ExceptionResponse
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from src.encoding import (
    decode_int16, decode_int32, decode_float, decode_complex,
    encode_int16, encode_int32, encode_float, encode_complex,
)

# --- Configuration ---
SMAPPEE_PORT = 502
DEFAULT_DEVICE_ID = 61       # Modbus unit/device ID — change if needed
TIMEOUT = 5

BUS_INFO_BASE   = 5248   # base address of device 0 bus info block
BUS_INFO_STRIDE = 32     # registers per device block
NUM_BUS_DEVICES = 10

GENERAL_CONFIG_PHANTOM_VOLTAGES = 4480
GENERAL_CONFIG_MODBUS_ADDRESS   = 4481

DEVICE_INFO_BASE = 5664  # device type, reserved, serial, FW minor, FW major

POWER_NUM_CHANNELS         = 28
POWER_ACTIVE_BASE          = 256   # total + fundamental active power, 1s avg
POWER_REACTIVE_BASE        = 384   # total + fundamental reactive power, 1s avg
POWER_APPARENT_BASE        = 768   # total + fundamental apparent power, 1s avg
POWER_INSTANTANEOUS_BASE   = 896   # instantaneous active power, 100 ms avg


def read_registers(client: ModbusTcpClient, address: int, count: int) -> list[int] | None:
    try:
        result = client.read_holding_registers(address=address, count=count, device_id=DEFAULT_DEVICE_ID)
    except ModbusException as e:
        print(f"  [exception] addr={address}: {e}")
        return None
    if result.isError():
        print(f"  [error] addr={address}: {result}")
        return None
    return result.registers


PHANTOM_VOLTAGE_MODES = {
    0: "disabled",
    1: "3-phase 120°",
    2: "2-phase 180°",
    3: "virtual star point",
}


def read_general_config(client: ModbusTcpClient) -> None:
    # --- phantom voltages + modbus address (4480–4481) ---
    regs = read_registers(client, address=GENERAL_CONFIG_PHANTOM_VOLTAGES, count=2)
    if regs is not None:
        phantom = decode_int16(regs, 0)
        modbus_addr = decode_int16(regs, 1)
        phantom_label = PHANTOM_VOLTAGE_MODES.get(phantom, f"unknown ({phantom})")
        print(f"  Phantom voltages : {phantom_label}")
        print(f"  Modbus address   : {modbus_addr}")

    # --- device info block (5664–5669) ---
    regs = read_registers(client, address=DEVICE_INFO_BASE, count=6)
    if regs is not None:
        device_type = decode_int16(regs, 0)
        serial      = decode_int32(regs, 2)
        fw_minor    = decode_int16(regs, 4)
        fw_major    = decode_int16(regs, 5)
        print(f"  Device type      : {device_type}")
        print(f"  Serial number    : {serial}")
        print(f"  Firmware version : {fw_major}.{fw_minor}")


def list_bus_devices(client: ModbusTcpClient) -> None:
    print(f"  {'Dev':>3}  {'DevType':>7}  {'Slots':>5}  {'Serial':>12}  {'FW':>8}")
    print("  " + "-" * 45)

    for dev in range(NUM_BUS_DEVICES):
        base = BUS_INFO_BASE + dev * BUS_INFO_STRIDE
        regs = read_registers(client, address=base, count=6)
        if regs is None:
            print(f"  {dev:>3}  (error)")
            continue
        device_type = decode_int16(regs, 0)
        slots       = decode_int16(regs, 1)
        serial      = decode_int32(regs, 2)
        fw_minor    = decode_int16(regs, 4)
        fw_major    = decode_int16(regs, 5)
        print(f"  {dev:>3}  {device_type:>7}  {slots:>5}  {serial:>12}  {fw_major}.{fw_minor:<6}")


def read_power(client: ModbusTcpClient) -> None:
    # Read all four sections in bulk (28 channels each)
    regs_active  = read_registers(client, address=POWER_ACTIVE_BASE,        count=POWER_NUM_CHANNELS * 4)
    regs_reactive = read_registers(client, address=POWER_REACTIVE_BASE,     count=POWER_NUM_CHANNELS * 4)
    regs_apparent = read_registers(client, address=POWER_APPARENT_BASE,     count=POWER_NUM_CHANNELS * 4)
    regs_instant  = read_registers(client, address=POWER_INSTANTANEOUS_BASE, count=POWER_NUM_CHANNELS * 2)

    header = (f"  {'Ch':>2}  {'Act.Tot':>10}  {'Act.Fund':>10}"
              f"  {'React.Tot':>10}  {'React.Fund':>10}"
              f"  {'App.Tot':>10}  {'App.Fund':>10}"
              f"  {'Instant':>10}")
    print(header)
    print("  " + "-" * (len(header) - 2))

    for ch in range(POWER_NUM_CHANNELS):
        act_tot  = decode_float(regs_active,   ch * 4)     if regs_active   else float('nan')
        act_fund = decode_float(regs_active,   ch * 4 + 2) if regs_active   else float('nan')
        rea_tot  = decode_float(regs_reactive, ch * 4)     if regs_reactive else float('nan')
        rea_fund = decode_float(regs_reactive, ch * 4 + 2) if regs_reactive else float('nan')
        app_tot  = decode_float(regs_apparent, ch * 4)     if regs_apparent else float('nan')
        app_fund = decode_float(regs_apparent, ch * 4 + 2) if regs_apparent else float('nan')
        instant  = decode_float(regs_instant,  ch * 2)     if regs_instant  else float('nan')

        print(f"  {ch:>2}  {act_tot:>10.2f}  {act_fund:>10.2f}"
              f"  {rea_tot:>10.2f}  {rea_fund:>10.2f}"
              f"  {app_tot:>10.2f}  {app_fund:>10.2f}"
              f"  {instant:>10.2f}")


def main():
    parser = argparse.ArgumentParser(description="Smappee Connect Tool")
    parser.add_argument("hostname", help="IP address or hostname of the Smappee device")
    args = parser.parse_args()

    host = args.hostname
    print(f"Connecting to {host}:{SMAPPEE_PORT} (device_id={DEFAULT_DEVICE_ID}) ...")
    client = ModbusTcpClient(host=host, port=SMAPPEE_PORT, timeout=TIMEOUT)

    if not client.connect():
        print("Connection failed.")
        return

    print("Connected.\n")

    try:
        print("=== General Config ===")
        read_general_config(client)
        print()
        print("=== Bus Devices ===")
        list_bus_devices(client)
        print()
        print("=== Power (W / var / VA) ===")
        read_power(client)
    finally:
        client.close()
        print("\nConnection closed.")

if __name__ == "__main__":
    main()
