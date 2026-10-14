"""Order pricing. All amounts are integer cents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Line:
    unit_cents: int
    quantity: int
    category: str = "general"


@dataclass
class Customer:
    tier: str = "standard"  # "standard", "silver", "gold"
    country: str = "DE"


def price_order(lines: list[Line], customer: Customer, coupon_percent: int = 0) -> int:
    subtotal = 0
    for line in lines:
        subtotal += line.unit_cents * line.quantity
    if subtotal == 0:
        return 0
    discount = 0
    if customer.tier == "gold":
        discount = subtotal * 10 // 100
        if subtotal > 100_000:
            discount += 2_000
    elif customer.tier == "silver":
        discount = subtotal * 5 // 100
    else:
        if subtotal > 50_000:
            discount = subtotal * 2 // 100
    if coupon_percent > 0:
        if customer.tier == "gold":
            coupon_percent = min(coupon_percent, 15)
        elif customer.tier == "silver":
            coupon_percent = min(coupon_percent, 10)
        else:
            coupon_percent = min(coupon_percent, 20)
        after_tier = subtotal - discount
        discount += after_tier * coupon_percent // 100
    net = subtotal - discount
    tax_rate = 19
    if customer.country == "DE":
        tax_rate = 19
    elif customer.country == "FR":
        tax_rate = 20
    elif customer.country == "CH":
        tax_rate = 0
    else:
        tax_rate = 21
    food = sum(line.unit_cents * line.quantity for line in lines if line.category == "food")
    if food and customer.country == "DE" and food * 100 // subtotal >= 50:
        net_food_share = net * food // subtotal
        tax = net_food_share * 7 // 100 + (net - net_food_share) * tax_rate // 100
    else:
        tax = net * tax_rate // 100
    total = net + tax
    if total % 5 == 4 and total > 1_000:
        total += 1
    return total
