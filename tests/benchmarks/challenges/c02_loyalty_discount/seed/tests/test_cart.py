from cart import Cart, Customer


def make_cart(coupon: int = 0) -> Cart:
    cart = Cart(Customer(1, "Asha", orders_placed=3, member_since_year=2022), coupon_percent=coupon)
    cart.add("mug", 1_200, 2)
    cart.add("tea", 800)
    return cart


def test_subtotal_and_shipping() -> None:
    cart = make_cart()
    assert cart.subtotal_cents() == 3_200
    assert cart.shipping_cents() == 499
    assert cart.total_cents() == 3_699


def test_a_coupon_reduces_the_goods_not_the_shipping() -> None:
    assert make_cart(coupon=10).total_cents() == 2_880 + 499
