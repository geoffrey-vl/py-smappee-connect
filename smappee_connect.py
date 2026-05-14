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
        list_bus_devices(client)
    finally:
        client.close()
        print("\nConnection closed.")

if __name__ == "__main__":
    main()
