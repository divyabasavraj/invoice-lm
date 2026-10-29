"""GSTIN structure, checksum and state codes.

A GSTIN is 15 characters: 2-digit state code + 10-character PAN + entity
number (1-9, A-Z) + 'Z' + a check character computed over the first 14.
"""

import random
import re
import string

CHARSET = string.digits + string.ascii_uppercase  # 36 symbols

STATE_CODES: dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}

_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def check_char(first14: str) -> str:
    """Check character for the first 14 characters of a GSTIN."""
    total = 0
    for i, ch in enumerate(first14):
        product = CHARSET.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return CHARSET[(36 - total % 36) % 36]


def is_valid(gstin: str) -> bool:
    """Format, known state code and checksum all pass."""
    return (
        bool(_PATTERN.match(gstin))
        and gstin[:2] in STATE_CODES
        and check_char(gstin[:14]) == gstin[14]
    )


def random_pan(rng: random.Random, holder: str = "C") -> str:
    """Random PAN. 4th char is holder type (C company, P person, F firm...)."""
    letters = string.ascii_uppercase
    return (
        "".join(rng.choice(letters) for _ in range(3))
        + holder
        + rng.choice(letters)
        + "".join(rng.choice(string.digits) for _ in range(4))
        + rng.choice(letters)
    )


def random_gstin(rng: random.Random, state_code: str, holder: str = "C") -> str:
    first14 = state_code + random_pan(rng, holder) + rng.choice("1112349") + "Z"
    return first14 + check_char(first14)
