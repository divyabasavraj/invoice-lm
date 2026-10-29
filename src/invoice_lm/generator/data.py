"""Random but internally consistent GST invoices (the ground-truth labels).

Every number is computed here, so a label is always correct by construction:
line tax = taxable value x rate, intra-state splits into CGST + SGST, inter-state
uses IGST, and the grand total is rounded to the rupee with a round-off line.
"""

import random
from datetime import date, timedelta

from invoice_lm.gstin import STATE_CODES, random_gstin
from invoice_lm.schema import GSTInvoice, LineItem, Party, SupplyType, Totals

# GST 2.0: from this date most goods moved to the 5% / 18% slabs (12% and 28%
# mostly removed). Rates below are the generator's best understanding; check
# them against the CBIC rate notifications before publishing the dataset.
GST_REFORM_DATE = date(2025, 9, 22)

# (description, HSN/SAC, unit, GST % before the reform, price range in rupees)
CATALOG: list[tuple[str, str, str, float, tuple[float, float]]] = [
    ("Basmati Rice 25kg Bag", "1006", "BAG", 5, (1400, 2600)),
    ("Refined Sunflower Oil 15L", "1512", "TIN", 5, (1700, 2400)),
    ("Toor Dal", "0713", "KG", 0, (110, 180)),
    ("Masala Tea 1kg", "0902", "PKT", 5, (350, 700)),
    ("A4 Copier Paper 75 GSM", "4802", "REAM", 12, (230, 340)),
    ("Ball Pen (Box of 50)", "9608", "BOX", 18, (180, 450)),
    ("Corrugated Carton Box", "4819", "PCS", 12, (18, 75)),
    ("PVC Pipe 4 inch 6m", "3917", "PCS", 18, (480, 1100)),
    ("Cement OPC 53 Grade 50kg", "2523", "BAG", 28, (360, 450)),
    ("TMT Steel Bar 12mm", "7214", "KG", 18, (58, 75)),
    ("Ceiling Fan 1200mm", "8414", "PCS", 18, (1500, 3200)),
    ("Copper Wire 1.5 sq mm 90m", "8544", "COIL", 18, (1300, 2100)),
    ("Laptop 14 inch i5", "8471", "PCS", 18, (42000, 68000)),
    ("Wireless Mouse", "8471", "PCS", 18, (350, 900)),
    ("Split AC 1.5 Ton", "8415", "PCS", 28, (31000, 45000)),
    ("Cotton Shirt", "6205", "PCS", 5, (450, 990)),
    ("Leather Shoes", "6403", "PAIR", 18, (700, 3500)),
    ("Paracetamol 500mg Strip", "3004", "STRIP", 12, (18, 35)),
    ("Hand Sanitizer 500ml", "3808", "BTL", 18, (120, 260)),
    ("Plastic Chair", "9401", "PCS", 18, (450, 900)),
    ("Office Table", "9403", "PCS", 18, (4500, 12000)),
    ("Annual Maintenance Contract", "998713", "NOS", 18, (5000, 40000)),
    ("Freight Charges (GTA)", "996511", "TRIP", 5, (2500, 18000)),
    ("Consulting Services", "998311", "HRS", 18, (1500, 4000)),
    ("Housekeeping Services", "998533", "MONTH", 18, (12000, 45000)),
]

_NAME_A = ["Shree", "Sri", "Om", "Ganesh", "Lakshmi", "Bharat", "Sai", "Annapurna",
           "Krishna", "Vinayaka", "Navkar", "Balaji", "Kaveri", "Sahyadri", "Ganga"]
_NAME_B = ["Traders", "Enterprises", "Agencies", "Industries", "Distributors",
           "Stores", "Suppliers", "Corporation", "& Sons", "Marketing", "Solutions"]
_SUFFIX = ["", "", " Pvt Ltd", " LLP", " Private Limited"]
_STREETS = ["MG Road", "Station Road", "Gandhi Nagar", "Industrial Area Phase 2",
            "Market Yard", "Nehru Street", "Ring Road", "APMC Yard", "Main Bazaar"]
# Cities per state code, for states the generator uses most.
_CITIES = {
    "29": ["Bengaluru", "Mysuru", "Hubballi", "Mangaluru", "Belagavi"],
    "27": ["Mumbai", "Pune", "Nagpur", "Nashik"],
    "33": ["Chennai", "Coimbatore", "Madurai"],
    "07": ["New Delhi"],
    "24": ["Ahmedabad", "Surat", "Vadodara"],
    "36": ["Hyderabad", "Warangal"],
    "09": ["Lucknow", "Noida", "Kanpur"],
    "19": ["Kolkata", "Howrah"],
    "32": ["Kochi", "Thiruvananthapuram"],
    "08": ["Jaipur", "Udaipur"],
}
_COMMON_STATES = list(_CITIES)
# First three PIN digits per state (rough ranges), so the PIN fits the city.
_PIN_PREFIX = {"29": (560, 591), "27": (400, 445), "33": (600, 643), "07": (110, 110),
               "24": (360, 396), "36": (500, 509), "09": (201, 285), "19": (700, 743),
               "32": (670, 695), "08": (302, 345)}


def _party(rng: random.Random, state_code: str, with_gstin: bool = True) -> Party:
    holder = rng.choice("CCCFFP")
    name = f"{rng.choice(_NAME_A)} {rng.choice(_NAME_B)}{rng.choice(_SUFFIX) if holder == 'C' else ''}"
    city = rng.choice(_CITIES.get(state_code, ["City"]))
    lo, hi = _PIN_PREFIX.get(state_code, (110, 855))
    pin = f"{rng.randint(lo, hi)}{rng.randint(1, 99):03d}"
    address = f"{rng.randint(1, 450)}, {rng.choice(_STREETS)}, {city} - {pin}"
    return Party(
        name=name,
        gstin=random_gstin(rng, state_code, holder) if with_gstin else None,
        address=address,
        state=STATE_CODES[state_code],
        state_code=state_code,
    )


def _invoice_number(rng: random.Random, d: date) -> str:
    fy = d.year if d.month >= 4 else d.year - 1
    style = rng.randrange(4)
    n = rng.randint(1, 4999)
    if style == 0:
        return f"INV/{fy % 100}-{(fy + 1) % 100}/{n:04d}"
    if style == 1:
        return f"{rng.choice(['ST', 'TI', 'GST'])}-{n}"
    if style == 2:
        return f"{fy}{(fy + 1) % 100}/{n:05d}"
    return str(n)


# Items whose rate changed on GST_REFORM_DATE.
POST_REFORM_RATE = {
    "A4 Copier Paper 75 GSM": 18,
    "Corrugated Carton Box": 5,
    "Cement OPC 53 Grade 50kg": 18,
    "Split AC 1.5 Ton": 18,
    "Paracetamol 500mg Strip": 5,
}


def gst_rate_for(desc: str, base_rate: float, unit_price: float, d: date) -> float:
    post = d >= GST_REFORM_DATE
    if desc == "Leather Shoes":  # footwear rate depends on the price per pair
        return (5 if unit_price <= 2500 else 18) if post else (12 if unit_price <= 1000 else 18)
    return POST_REFORM_RATE.get(desc, base_rate) if post else base_rate


def _line(rng: random.Random, intra: bool, product, d: date) -> LineItem:
    desc, hsn, unit, base_rate, (lo, hi) = product
    qty = rng.choice([1, 1, 2, 3, 4, 5, 6, 10, 12, 20, 25, 50, 100])
    if hi > 20000 or unit in {"MONTH", "TRIP"}:
        qty = rng.choice([1, 1, 1, 2, 3])
    rate = round(rng.uniform(lo, hi), rng.choice([0, 0, 2]))
    gst_rate = gst_rate_for(desc, base_rate, rate, d)
    taxable = round(qty * rate, 2)
    tax = taxable * gst_rate / 100
    if intra:
        half = round(tax / 2, 2)
        cgst, sgst, igst = half, half, None
        line_tax = 2 * half
    else:
        cgst, sgst, igst = None, None, round(tax, 2)
        line_tax = igst
    return LineItem(
        description=desc, hsn_sac=hsn, quantity=qty, unit=unit, rate=rate,
        taxable_value=taxable, gst_rate=gst_rate, cgst_amount=cgst,
        sgst_amount=sgst, igst_amount=igst, total=round(taxable + line_tax, 2),
    )


def random_invoice(rng: random.Random) -> GSTInvoice:
    supplier_state = rng.choice(_COMMON_STATES)
    intra = rng.random() < 0.65
    buyer_state = supplier_state if intra else rng.choice(
        [s for s in _COMMON_STATES if s != supplier_state])
    d = date(2025, 4, 1) + timedelta(days=rng.randint(0, 540))
    products = rng.sample(CATALOG, rng.choice([1, 2, 2, 3, 3, 4, 5, 6, 8]))
    items = [_line(rng, intra, p, d) for p in products]

    taxable = round(sum(i.taxable_value for i in items), 2)
    cgst = round(sum(i.cgst_amount or 0 for i in items), 2)
    sgst = round(sum(i.sgst_amount or 0 for i in items), 2)
    igst = round(sum(i.igst_amount or 0 for i in items), 2)
    exact = taxable + cgst + sgst + igst
    grand = float(round(exact))
    return GSTInvoice(
        invoice_number=_invoice_number(rng, d),
        invoice_date=d,
        supplier=_party(rng, supplier_state),
        buyer=_party(rng, buyer_state, with_gstin=rng.random() < 0.9),
        place_of_supply=f"{STATE_CODES[buyer_state]} ({buyer_state})",
        supply_type=SupplyType.INTRA_STATE if intra else SupplyType.INTER_STATE,
        reverse_charge=False,
        line_items=items,
        totals=Totals(taxable_value=taxable, cgst=cgst, sgst=sgst, igst=igst,
                      round_off=round(grand - exact, 2), grand_total=grand),
    )
