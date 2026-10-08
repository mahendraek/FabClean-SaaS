from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

def now_utc():
    return datetime.now(timezone.utc)

PricingType = Literal["per_item","per_lb","per_kg","per_pair","per_panel","flat","starting_at","quote"]
FulfillmentType = Literal["walk_in","pickup_only","delivery_only","pickup_and_delivery"]

class ServiceVariant(BaseModel):
    id: str
    name: str
    price: float
    active: bool = True

class Modifier(BaseModel):
    id: str
    name: str
    amount: float = 0
    amount_type: Literal["flat","percent"] = "flat"
    customer_selectable: bool = True
    active: bool = True

class Service(BaseModel):
    id: str
    business_id: str = "fabclean"
    category: str
    name: str
    description: str = ""
    pricing_type: PricingType
    base_price: float = 0
    minimum_price: float = 0
    unit_label: str = ""
    turnaround_hours: int = 48
    taxable: bool = False
    tax_rate: float = 0
    express_enabled: bool = False
    express_surcharge_percent: float = 0
    active: bool = True
    pickup_eligible: bool = True
    delivery_eligible: bool = True
    reward_eligible: bool = True
    subscription_eligible: bool = False
    variants: List[ServiceVariant] = Field(default_factory=list)
    modifiers: List[Modifier] = Field(default_factory=list)

class OrderItem(BaseModel):
    service_id: str
    service_name: str
    quantity: float = 1
    unit_price: float = 0
    unit_label: str = "item"
    modifiers: List[str] = Field(default_factory=list)
    notes: str = ""
    barcode_value: Optional[str] = None

class CustomerBase(BaseModel):
    name: str
    phone: str
    email: str = ""
    notes: str = ""

class CustomerCreate(CustomerBase):
    business_id: str = "fabclean"
    location_id: str = "main"

class Customer(CustomerBase):
    id: str
    business_id: str = "fabclean"
    location_id: str = "main"
    reward_points: int = 0
    order_count: int = 0
    lifetime_value: float = 0
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

class OrderCreate(BaseModel):
    customer_id: Optional[str] = None
    customer_name: str
    customer_phone: str
    customer_email: str = ""
    fulfillment_type: FulfillmentType = "walk_in"
    items: List[OrderItem] = Field(default_factory=list)
    notes: str = ""
    discount: float = 0
    tax: float = 0
    payment_method: str = "cash"
    payment_status: str = "unpaid"
    quick_dropoff: bool = False
    bag_count: int = 0
    due_at: Optional[datetime] = None
    pricing_status: Literal["estimated","final"] = "estimated"
    service_area_id: Optional[str] = None
    service_area_name: str = ""
    scheduled_slot_id: Optional[str] = None
    scheduled_slot_label: str = ""
    pickup_date: str = ""
    pickup_slot_id: Optional[str] = None
    pickup_slot_label: str = ""
    delivery_date: str = ""
    delivery_slot_id: Optional[str] = None
    delivery_slot_label: str = ""
    service_address: str = ""
    service_postal_code: str = ""
    delivery_fee: float = 0
    promo_code: str = ""
    offer_id: Optional[str] = None

class Order(BaseModel):
    id: str
    business_id: str = "fabclean"
    location_id: str = "main"
    order_number: str
    barcode_value: str
    customer: Customer
    fulfillment_type: FulfillmentType
    status: str = "received"
    items: List[OrderItem]
    subtotal: float
    discount: float = 0
    tax: float = 0
    total: float
    payment_method: str = "cash"
    payment_status: str = "unpaid"
    notes: str = ""
    quick_dropoff: bool = False
    bag_count: int = 0
    due_at: Optional[datetime] = None
    pricing_status: Literal["estimated","final"] = "estimated"
    service_area_id: Optional[str] = None
    service_area_name: str = ""
    scheduled_slot_id: Optional[str] = None
    scheduled_slot_label: str = ""
    pickup_date: str = ""
    pickup_slot_id: Optional[str] = None
    pickup_slot_label: str = ""
    delivery_date: str = ""
    delivery_slot_id: Optional[str] = None
    delivery_slot_label: str = ""
    service_address: str = ""
    service_postal_code: str = ""
    delivery_fee: float = 0
    promo_code: str = ""
    offer_id: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)
