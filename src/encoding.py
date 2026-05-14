import struct


# ---------------------------------------------------------------------------
# Decode helpers  (registers → Python value)
# ---------------------------------------------------------------------------

def decode_int16(registers: list[int], offset: int = 0) -> int:
    """Signed Int16 from one register (big-endian)."""
    raw = registers[offset]
    return raw if raw < 0x8000 else raw - 0x10000


def decode_int32(registers: list[int], offset: int = 0) -> int:
    """Signed Int32 from two registers (low word first)."""
    raw = (registers[offset + 1] << 16) | registers[offset]
    return raw if raw < 0x80000000 else raw - 0x100000000


def decode_float(registers: list[int], offset: int = 0) -> float:
    """Single-precision IEEE float from two registers (low word first)."""
    return struct.unpack('>f', struct.pack('>HH', registers[offset + 1], registers[offset]))[0]


def decode_complex(registers: list[int], offset: int = 0) -> complex:
    """Complex number from four registers (real then imaginary, each low word first)."""
    real = decode_float(registers, offset)
    imag = decode_float(registers, offset + 2)
    return complex(real, imag)


# ---------------------------------------------------------------------------
# Encode helpers  (Python value → registers)
# ---------------------------------------------------------------------------

def encode_int16(value: int) -> list[int]:
    """Encode signed Int16 as one register."""
    return [value & 0xFFFF]


def encode_int32(value: int) -> list[int]:
    """Encode signed Int32 as two registers (low word first)."""
    raw = value & 0xFFFFFFFF
    return [raw & 0xFFFF, (raw >> 16) & 0xFFFF]


def encode_float(value: float) -> list[int]:
    """Encode single-precision IEEE float as two registers (low word first)."""
    raw = struct.unpack('>I', struct.pack('>f', value))[0]
    return [raw & 0xFFFF, (raw >> 16) & 0xFFFF]


def encode_complex(value: complex) -> list[int]:
    """Encode complex number as four registers (real then imaginary, each low word first)."""
    return encode_float(value.real) + encode_float(value.imag)
