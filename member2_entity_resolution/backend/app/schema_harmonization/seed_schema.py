"""Hand-written SEED of the canonical electronics schema (version 1).
The schema then GROWS from data (see schema_growth.py). Edit freely, but keep ids snake_case."""

SEED_ATTRIBUTES = {
    "brand": {
        "aliases": ["brand", "manufacturer", "make", "vendor"],
        "examples": ["Kingston", "Corsair", "Seagate"],
    },
    "model": {
        "aliases": ["model", "model number", "model no", "part number", "mpn"],
        "examples": ["CMK16GX4M2B3200C16", "ST2000DM001", "HX424C15FB2/8"],
    },
    "capacity": {
        "aliases": ["capacity", "storage capacity", "total capacity", "drive capacity", "disk capacity"],
        "examples": ["8 GB", "1 TB", "256GB"],
    },
    "memory_type": {
        "aliases": ["memory type", "ram type", "memory technology"],
        "examples": ["DDR4", "DDR3", "SDRAM"],
    },
    "speed": {
        "aliases": ["speed", "memory speed", "clock speed", "data rate"],
        "examples": ["2400 MHz", "3200 MHz", "1600MHz"],
    },
    "form_factor": {
        "aliases": ["form factor", "form", "drive form factor", "dimm type"],
        "examples": ["DIMM", "SO-DIMM", "3.5 inch", "ATX"],
    },
    "interface": {
        "aliases": ["interface", "connectivity", "host interface", "connection"],
        "examples": ["SATA III", "USB 3.0", "PCIe"],
    },
    "color": {
        "aliases": ["color", "colour"],
        "examples": ["Black", "Red", "Silver"],
    },
    "weight": {
        "aliases": ["weight", "item weight", "product weight"],
        "examples": ["1.2 kg", "450 g"],
    },
    "warranty": {
        "aliases": ["warranty", "warranty period", "manufacturer warranty"],
        "examples": ["3 years", "Lifetime", "5 Year Limited"],
    },
}