from shipping import Destination, Parcel, shipping_cost


def test_small_parcel_in_germany() -> None:
    assert shipping_cost(Parcel(500, 2000), Destination()) == 495


def test_free_shipping_over_150_euro() -> None:
    assert shipping_cost(Parcel(800, 16000), Destination()) == 0
