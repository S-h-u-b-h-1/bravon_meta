def refund_total(unit_price, quantity):
    if quantity < 0:
        raise ValueError("quantity must not be negative")
    return unit_price * quantity
