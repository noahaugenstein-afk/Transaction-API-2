"""Pydantic models describing a commercial real-estate transaction.

These are the *friendly* field names your custom GPT sends. The field_mapper
translates them into the worksheet's AcroForm field names (e.g. "Text102"),
so the GPT never has to know Adobe's internal names.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Party(BaseModel):
    name: Optional[str] = Field(None, description="Company / entity legal name (landlord or tenant entity)")
    company: Optional[str] = Field(None, description="Company name if different from the entity name")
    prefix: Optional[str] = Field(None, description="Contact prefix: Mr., Ms., Mrs., Miss")
    first_name: Optional[str] = Field(None, description="Contact first name")
    last_name: Optional[str] = Field(None, description="Contact last name")
    contact: Optional[str] = Field(None, description="Full contact name if not split into first/last")
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    suite: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None


class Broker(BaseModel):
    name: Optional[str] = Field(None, description="Broker / agent full name")
    company: Optional[str] = Field(None, description="Brokerage company, e.g. Lee & Associates")
    side: Optional[str] = Field(None, description="'Listing'/'Landlord' or 'Procuring'/'Tenant'")
    license_id: Optional[str] = Field(None, description="DRE license number")
    commission_percent: Optional[float] = Field(None, description="This broker's share of the fee, %")


class PropertyInfo(BaseModel):
    name: Optional[str] = Field(None, description="Property / building name")
    address: Optional[str] = None
    suite: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    rentable_sf: Optional[float] = Field(None, description="Rentable square feet of the leased premises")
    total_building_sf: Optional[float] = Field(None, description="Total building square feet")
    building_class: Optional[str] = Field(None, description="Building class: A, B, C, Other")


class Financials(BaseModel):
    rate_per_sf: Optional[float] = Field(None, description="Starting rate per SF per month")
    rent_type: Optional[str] = Field(None, description="G, FSG, MG, NNN, MN, Other")
    effective_rate: Optional[float] = Field(None, description="Effective (blended) rate per SF")
    monthly_rent: Optional[float] = Field(None, description="Starting fixed monthly rent")
    annual_rent: Optional[float] = None
    security_deposit: Optional[float] = None
    free_rent: Optional[str] = Field(None, description="e.g. '3 Months'")
    ti_allowance: Optional[str] = Field(None, description="Tenant improvement allowance, e.g. '$20/SF'")
    parking_ratio: Optional[str] = Field(None, description="Parking ratio or permit count")
    total_lease_consideration: Optional[float] = Field(
        None, description="Total rent over the term, used as commission base"
    )


class Transaction(BaseModel):
    """Top-level structured transaction the GPT assembles from the lease."""

    transaction_type: Optional[str] = Field(None, description="Sale, Lease, Franchise, Consulting/Referral, Other")
    property_type: Optional[str] = Field(None, description="Office, Retail, Industrial, Land, Apartment, Other")
    lease_type: Optional[str] = Field(None, description="Direct, Sublease, Renewal, Expansion, Other")
    lee_exclusive: Optional[str] = Field(None, description="Whether this is a Lee exclusive: Yes or No")
    landlord: Party = Party()
    tenant: Party = Party()
    property: PropertyInfo = PropertyInfo()
    financials: Financials = Financials()

    lease_commencement: Optional[str] = Field(None, description="ISO date or as written")
    lease_expiration: Optional[str] = None
    lease_term_months: Optional[int] = None

    listing_broker: Broker = Broker()
    procuring_broker: Broker = Broker()

    total_commission_percent: Optional[float] = Field(None, description="Total fee %")
    total_commission_amount: Optional[float] = Field(None, description="Total fee $")

    notes: Optional[str] = None


class FillRequest(BaseModel):
    transaction: Transaction
    template: Optional[str] = Field(
        None, description="Override template filename in templates/. Defaults to commission worksheet."
    )
    flatten: bool = Field(
        True, description="If true, the returned PDF's fields are read-only (recommended for sharing)."
    )


class FillResponse(BaseModel):
    download_url: str
    filename: str
    expires_in_minutes: int
    fields_filled: int
    fields_skipped: list[str] = []
