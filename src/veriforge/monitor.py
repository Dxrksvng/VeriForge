"""Periodic probes and deterministic recovery of the local approved target."""

import logging
import time

from veriforge.db import connect
from veriforge.runtime import observe

log = logging.getLogger("veriforge.monitor")


def tick():
    with connect() as conn:
        active = conn.execute("SELECT id FROM deployments WHERE status='ACTIVE'").fetchall()
    for row in active:
        observe(row["id"], "runtime-verifier")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            tick()
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("Observation failed; health has not been established")
        time.sleep(30)
