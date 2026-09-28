"""Trusted acceptance suite. The candidate cannot replace this file."""
import json
import policy

results = []


def check(name, fn):
    try:
        fn()
        results.append({"name": name, "status": "PASS"})
    except Exception as e:
        results.append({"name": name, "status": "FAIL", "detail": str(e)[:300]})


def equal(actual, expected):
    assert actual == expected, f"expected {expected!r}, observed {actual!r}"


def conflict():
    try:
        policy.should_post("12550:THB", "99900:THB")
    except ValueError:
        return
    raise AssertionError("same key with different payload was accepted")


def invalid_amount():
    for v in (-1, 0, 1.5, True):
        try:
            policy.fee_minor(v)
        except ValueError:
            continue
        raise AssertionError(f"accepted invalid amount {v!r}")


check("FIN-RETRY-001", lambda: equal(policy.should_post("12550:THB", "12550:THB"), False))
check("FIN-NEW-001", lambda: equal(policy.should_post(None, "12550:THB"), True))
check("FIN-CONFLICT-001", conflict)
check("FIN-AMOUNT-001", invalid_amount)
for amount in (1,49,50,99,100,12550,99999,100000000):
    check(f"FIN-FEE-{amount}", lambda a=amount: equal(policy.fee_minor(a), (a+50)//100))
print(json.dumps({"suite":"financial-policy-v1","tests":results}))
