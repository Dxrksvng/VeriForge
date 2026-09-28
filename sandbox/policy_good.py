def fee_minor(amount_minor):
    if type(amount_minor) is not int or amount_minor <= 0:
        raise ValueError("positive integer required")
    return (amount_minor + 50) // 100


def should_post(existing_payload, incoming_payload):
    if existing_payload is None:
        return True
    if existing_payload != incoming_payload:
        raise ValueError("idempotency conflict")
    return False
