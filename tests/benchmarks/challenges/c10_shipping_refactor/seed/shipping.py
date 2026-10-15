"""Shipping cost for an order. All amounts are integer cents; weights are grams."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Parcel:
    weight_g: int
    value_cents: int
    fragile: bool = False


@dataclass
class Destination:
    country: str = "DE"
    island: bool = False
    express: bool = False


def shipping_cost(parcel: Parcel, destination: Destination) -> int:
    if parcel.weight_g <= 0:
        return 0
    if destination.country == "DE":
        if parcel.weight_g <= 1000:
            base = 495
        elif parcel.weight_g <= 5000:
            base = 695
        else:
            base = 695 + ((parcel.weight_g - 5000 + 999) // 1000) * 150
    elif destination.country in ("AT", "CH", "FR", "NL"):
        if parcel.weight_g <= 2000:
            base = 995
        else:
            base = 995 + ((parcel.weight_g - 2000 + 999) // 1000) * 250
    else:
        base = 1995 + ((parcel.weight_g + 999) // 1000) * 400
    if destination.island:
        base += 450
        if parcel.weight_g > 10000:
            base += 900
    if parcel.fragile:
        base += max(250, base * 8 // 100)
    if destination.express:
        base = base * 2
        if destination.country != "DE":
            base += 500
    # free shipping over 150 EUR within Germany, except heavy parcels and islands
    if (
        destination.country == "DE"
        and parcel.value_cents >= 15000
        and parcel.weight_g <= 10000
        and not destination.island
    ):
        return 0
    # round up to the next 5 cents
    return (base + 4) // 5 * 5
