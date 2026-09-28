import logging
import time

from veriforge.workflow import work_once

logging.basicConfig(level=logging.INFO)
if __name__ == "__main__":
    while True:
        try:
            if not work_once():
                time.sleep(2)
        except KeyboardInterrupt:
            break
        except Exception:
            logging.exception("Worker failed; leased jobs remain recoverable")
            time.sleep(3)
