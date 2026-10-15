"""Money validation and order totals, without tax calculation or providers."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fastapi import HTTPException


def number(value, label='Amount'):
    if isinstance(value, bool):
        raise HTTPException(400, label+' must be a finite non-negative number')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(400, 'Invalid '+label.lower())
    if not result.is_finite() or result < 0 or result > Decimal('100000000'):
        raise HTTPException(400, 'Invalid '+label.lower())
    return result


def money(value):
    return number(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def quote(items, discount=0, delivery_fee=0):
    if not isinstance(items, list) or len(items) > 500:
        raise HTTPException(400, 'Invalid order items')
    subtotal = Decimal(0)
    for item in items:
        if not isinstance(item, dict):
            raise HTTPException(400, 'Invalid order item')
        quantity = number(item.get('quantity', 1), 'Quantity')
        if quantity <= 0:
            raise HTTPException(400, 'Quantity must be greater than zero')
        subtotal += money(quantity * number(item.get('unit_price', 0), 'Unit price'))
    reduction, fee = money(discount), money(delivery_fee)
    if reduction > subtotal:
        raise HTTPException(400, 'Discount exceeds the item subtotal')
    return {'subtotal': float(subtotal), 'discount': float(reduction),
            'delivery_fee': float(fee), 'total': float(subtotal-reduction+fee)}


def validate_refund(order, rows, amount):
    gross = money(amount)
    net_paid = sum(Decimal(str(row['amount'])) for row in rows)
    refunded = sum(abs(Decimal(str(row['amount']))) for row in rows if row.get('transaction_type') == 'refund')
    if gross <= 0 or gross > net_paid or gross + refunded > money(order.get('total', 0)):
        raise HTTPException(409, 'Refund exceeds the paid balance or unrefunded order total')
