"""Camera card in -> proposal ready. While the website runs on the Resolve PC, this looks for a camera card every
10 s (autoedit/offload.find_cards: Sony PRIVATE/M4ROOT or DCIM on a removable drive). A card that appears starts one
job `autoedit card`: offload to _Inbox (checked, card untouched), then per new day an edit '<date> voorstel' with a
plan. Off with `card_auto: false` in config.yaml."""
from __future__ import annotations

import threading
import time

from . import query

POLL_S = 10


def start(host, poll: float = POLL_S, find=None) -> threading.Thread | None:
    """Start the watcher thread (daemon). Returns None when it is switched off."""
    if query._cfg().get("card_auto", True) is False:
        return None
    if find is None:
        import sys
        sys.path.insert(0, str(query.REPO))
        from autoedit.offload import find_cards as find

    def loop():
        seen: set[str] = set()
        while True:
            try:
                now = {str(c) for c in find()}
            except Exception:
                now = seen
            for card in sorted(now - seen):                      # a card that just went in: one job per card
                try:
                    host.run(["autoedit", "card"], f"Kaart gevonden ({card}): offloaden + voorstel", None)
                except Exception:
                    pass
            seen = now
            time.sleep(poll)

    t = threading.Thread(target=loop, name="cardwatch", daemon=True)
    t.start()
    return t
