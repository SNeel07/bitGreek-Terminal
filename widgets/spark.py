"""
spark.py — Sparkline Generator
===============================
Converts a rolling OI history (list of dicts from store.py) into a
5-character unicode sparkline string like ▁▂▄▇█

This is not a Textual widget — it's a pure function that returns a string.
The string gets embedded directly inside the trend cell in oi_table.py.

Example output:
    ▁▁▂▄▇  (OI steadily building up)
    █▇▄▂▁  (OI unwinding)
    ▄▄▄▄▄  (flat / stale NSE data)
    ░░▁▂▄  (only 3 fetches so far, first 2 slots are empty placeholders)
"""

from typing import List, Dict

# Unicode block characters from shortest to tallest
SPARK_CHARS = "▁▂▃▄▅▆▇█"
EMPTY_CHAR  = "░"   # shown for slots with no data yet (< 5 fetches)
FLAT_CHAR   = "▄"   # shown when all values are identical (stale data)


def build_spark(history: List[Dict], key: str = "oi", length: int = 5) -> str:
    """
    Builds a sparkline string from the rolling history list.

    Args:
        history : list of dicts from store.get_history(strike, opt_type)
                  each dict has keys: oi, doi, price, volume
        key     : which field to plot — 'oi' (default) or 'price'
        length  : total character width of the sparkline (matches HISTORY_SIZE)

    Returns:
        A string of `length` unicode block characters, e.g. "░░▁▃▇"
    """
    # Pad with None on the left if we have fewer than `length` fetches yet
    padded = [None] * (length - len(history)) + [h.get(key, 0) for h in history]

    values = [v for v in padded if v is not None]

    if not values:
        return EMPTY_CHAR * length

    lo  = min(values)
    hi  = max(values)

    result = []
    for v in padded:
        if v is None:
            result.append(EMPTY_CHAR)
            continue

        if hi == lo:
            # All values identical — flat line, show mid-height
            result.append(FLAT_CHAR)
        else:
            # Normalise to 0–7 index into SPARK_CHARS
            idx = round((v - lo) / (hi - lo) * (len(SPARK_CHARS) - 1))
            result.append(SPARK_CHARS[idx])

    return "".join(result)