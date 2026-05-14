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

CT_NUM_CHANNELS      = 28
CT_VOLTAGE_BASE      = 4096   # CT associated voltage
CT_TYPE_BASE         = 4352   # CT type identifier
CT_SLOT_MAPPING_BASE = 4416   # CT slot mapping

CT_VOLTAGE_NAMES = {
    0:  "none",
    1:  "L1-N (Normal)",
    16: "L1-N (Reverse)",
    2:  "L2-N (Normal)",
    32: "L2-N (Reverse)",
    4:  "L3-N (Normal)",
    64: "L3-N (Reverse)",
    33: "L1-L2 (Normal)",
    18: "L1-L2 (Reverse)",
    66: "L2-L3 (Normal)",
    36: "L2-L3 (Reverse)",
    65: "L1-L3 (Normal)",
    20: "L1-L3 (Reverse)",
}

CT_TYPE_NAMES = {
    0:  "SCT01-50/100/200A",
    1:  "SCT01-400/800A",
    2:  "Rogowski 600A-100mV",
    3:  "SCT02-50A",
    4:  "SCT02-100A",
    5:  "SCT02-200A",
    6:  "SCT02-400A",
    7:  "SCT02-800A",
    8:  "SCT03-50A",
    9:  "SCT03-100A",
    10: "SCT03-200A",
    11: "Rogowski 400A-100mV",
    12: "Closed CT",
    13: "No phase adjustment",
    14: "No shift correction",
    15: "Rogowski 200A",
}

DEVICE_TYPE_NAMES = {
    5130: "Smappee Connect",
    5400: "Smappee Power Box",
    5520: "Smappee CT Hub",
    5600: "Smappee Solid Core 3-Phase CT",
}


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
        print(f"  Device type      : {DEVICE_TYPE_NAMES.get(device_type, f'unknown ({device_type})')}")
        print(f"  Serial number    : {serial}")
        print(f"  Firmware version : {fw_major}.{fw_minor}")


def list_bus_devices(client: ModbusTcpClient) -> None:
    print(f"  {'Dev':>3}  {'DevType':<30}  {'Slots':>5}  {'Serial':>12}  {'FW':>8}")
    print("  " + "-" * 65)

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
        type_str    = DEVICE_TYPE_NAMES.get(device_type, f"unknown ({device_type})")
        print(f"  {dev:>3}  {type_str:<30}  {slots:>5}  {serial:>12}  {fw_major}.{fw_minor:<6}")


def read_power(client: ModbusTcpClient, ct_map: dict[int, dict] | None = None) -> None:
    # Read all four sections in bulk (28 channels each)
    regs_active   = read_registers(client, address=POWER_ACTIVE_BASE,         count=POWER_NUM_CHANNELS * 4)
    regs_reactive = read_registers(client, address=POWER_REACTIVE_BASE,       count=POWER_NUM_CHANNELS * 4)
    regs_apparent = read_registers(client, address=POWER_APPARENT_BASE,       count=POWER_NUM_CHANNELS * 4)
    regs_instant  = read_registers(client, address=POWER_INSTANTANEOUS_BASE,  count=POWER_NUM_CHANNELS * 2)

    if ct_map is not None:
        channels = sorted(ch for ch in ct_map if ch < POWER_NUM_CHANNELS)
        name_w   = max((len(ct_map[ch]['label']) for ch in channels), default=10)
        header   = (f"  {'Name':<{name_w}}  {'Act.Tot':>10}  {'Act.Fund':>10}"
                    f"  {'React.Tot':>10}  {'React.Fund':>10}"
                    f"  {'App.Tot':>10}  {'App.Fund':>10}"
                    f"  {'Instant':>10}")
        print(header)
        print("  " + "-" * (len(header) - 2))
        for ch in channels:
            name     = ct_map[ch]['label']
            act_tot  = decode_float(regs_active,   ch * 4)     if regs_active   else float('nan')
            act_fund = decode_float(regs_active,   ch * 4 + 2) if regs_active   else float('nan')
            rea_tot  = decode_float(regs_reactive, ch * 4)     if regs_reactive else float('nan')
            rea_fund = decode_float(regs_reactive, ch * 4 + 2) if regs_reactive else float('nan')
            app_tot  = decode_float(regs_apparent, ch * 4)     if regs_apparent else float('nan')
            app_fund = decode_float(regs_apparent, ch * 4 + 2) if regs_apparent else float('nan')
            instant  = decode_float(regs_instant,  ch * 2)     if regs_instant  else float('nan')
            print(f"  {name:<{name_w}}  {act_tot:>10.2f}  {act_fund:>10.2f}"
                  f"  {rea_tot:>10.2f}  {rea_fund:>10.2f}"
                  f"  {app_tot:>10.2f}  {app_fund:>10.2f}"
                  f"  {instant:>10.2f}")
    else:
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


def read_ct_config(client: ModbusTcpClient, show_all: bool = True) -> dict[int, dict]:
    """Read CT configuration. Returns a mapping of slot → {voltage, type} for configured CTs."""
    regs_voltage = read_registers(client, address=CT_VOLTAGE_BASE,      count=CT_NUM_CHANNELS)
    regs_type    = read_registers(client, address=CT_TYPE_BASE,         count=CT_NUM_CHANNELS)
    regs_slot    = read_registers(client, address=CT_SLOT_MAPPING_BASE, count=CT_NUM_CHANNELS)

    if show_all:
        print(f"  {'CT':>2}  {'Voltage':<16}  {'Slot':>6}  Type")
        print("  " + "-" * 55)

    ct_map: dict[int, dict] = {}

    for ch in range(CT_NUM_CHANNELS):
        voltage = decode_int16(regs_voltage, ch) if regs_voltage else None
        ct_type = decode_int16(regs_type,    ch) if regs_type    else None
        slot    = decode_int16(regs_slot,    ch) if regs_slot    else None

        v_str    = CT_VOLTAGE_NAMES.get(voltage, f"unknown ({voltage})") if voltage is not None else "(err)"
        s_str    = f"{slot:>6}"    if slot    is not None else " (err)"
        type_str = CT_TYPE_NAMES.get(ct_type, f"unknown ({ct_type})") if ct_type is not None else "(err)"

        if show_all:
            print(f"  {ch:>2}  {v_str:<16}  {s_str}  {type_str}")

        if voltage is not None and voltage != 0 and slot is not None:
            ct_map[slot] = {'voltage': v_str, 'type': type_str, 'label': f"{v_str} [{type_str}]"}

    return ct_map


def main():
    parser = argparse.ArgumentParser(description="Smappee Connect Tool")
    parser.add_argument("hostname", help="IP address or hostname of the Smappee device")
    parser.add_argument("-a", "--all", action="store_true",
                        help="Show all channels and sections (general config, bus devices, full CT table)")
    args = parser.parse_args()

    host = args.hostname
    print(f"Connecting to {host}:{SMAPPEE_PORT} (device_id={DEFAULT_DEVICE_ID}) ...")
    client = ModbusTcpClient(host=host, port=SMAPPEE_PORT, timeout=TIMEOUT)

    if not client.connect():
        print("Connection failed.")
        return

    print("Connected.\n")

    try:
        if args.all:
            print("=== General Config ===")
            read_general_config(client)
            print()
            print("=== Bus Devices ===")
            list_bus_devices(client)
            print()
            print("=== CT Configuration ===")
            read_ct_config(client, show_all=True)
            print()
            print("=== Power (W / var / VA) ===")
            read_power(client)
        else:
            ct_map = read_ct_config(client, show_all=False)
            print("=== Power (W / var / VA) ===")
            read_power(client, ct_map=ct_map)
    finally:
        client.close()
        print("\nConnection closed.")

if __name__ == "__main__":
    main()
