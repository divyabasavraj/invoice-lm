"""Output schema for an Indian GST tax invoice.

This is what the model must produce and what the generator writes as the
ground-truth label. Money is in rupees, rounded to 2 decimals. Fields the
invoice doesn't show are null, never guessed.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0"


class SupplyType(StrEnum):
    INTRA_STATE = "intra_state"  # CGST + SGST
    INTER_STATE = "inter_state"  # IGST


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Party(_Strict):
    name: str
    gstin: str | None = Field(None, description="15-character GSTIN, as printed")
    address: str | None = None
    state: str | None = None
    state_code: str | None = Field(None, description="2-digit GST state code")


class LineItem(_Strict):
    description: str
    hsn_sac: str | None = Field(None, description="HSN (goods) or SAC (services) code")
    quantity: float | None = None
    unit: str | None = None
    rate: float | None = Field(None, description="Price per unit before tax")
    taxable_value: float
    gst_rate: float | None = Field(None, description="Total GST % (e.g. 18)")
    cgst_amount: float | None = None
    sgst_amount: float | None = None
    igst_amount: float | None = None
    total: float | None = Field(None, description="Taxable value plus tax for this line")

    @field_validator(
        "taxable_value", "rate", "cgst_amount", "sgst_amount", "igst_amount", "total"
    )
    @classmethod
    def _round_money(cls, v: float | None) -> float | None:
        return None if v is None else round(v, 2)


class Totals(_Strict):
    taxable_value: float
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    round_off: float = 0.0
    grand_total: float

    @field_validator("*")
    @classmethod
    def _round_money(cls, v: float) -> float:
        return round(v, 2)


class GSTInvoice(_Strict):
    invoice_number: str
    invoice_date: date
    supplier: Party
    buyer: Party
    place_of_supply: str | None = Field(None, description="State name or code, as printed")
    supply_type: SupplyType
    reverse_charge: bool = False
    line_items: list[LineItem] = Field(min_length=1)
    totals: Totals


def json_schema() -> dict:
    """JSON schema handed to the model (and to Gemini/Ollama baselines)."""
    return GSTInvoice.model_json_schema()


def decoding_schema() -> dict:
    """json_schema() with every property required (nullable ones stay nullable).

    Constrained decoders (Ollama, llama.cpp grammars) may skip properties that
    aren't required, so the model silently drops optional fields. Requiring
    them all makes the model write an explicit value or null for each one.
    """
    def fix(node):
        if isinstance(node, dict):
            node.pop("default", None)
            node.pop("title", None)
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"])
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)
        return node

    s = fix(json_schema())
    # A "format: date" grammar forces four year digits first, so the model copies
    # a printed 27/01/2026 as "2701-01-26". Let it write the date as printed;
    # validators._coerce turns day-first dates into ISO.
    s["properties"]["invoice_date"].pop("format", None)
    return s
