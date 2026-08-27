import re
from collections import deque
from typing import Dict, Any, List, Optional
import logging

HISTORY_SIZE = 5
_DATE_CACHE  = {}

MONTHS = {
    "jan":"01","feb":"02","mar":"03","apr":"04",
    "may":"05","jun":"06","jul":"07","aug":"08",
    "sep":"09","oct":"10","nov":"11","dec":"12"
}

# Reverse map for display: month number → abbreviated name
MONTH_NAMES = {v: k.capitalize() for k, v in MONTHS.items()}


def safe_float(val) -> float:
    try:
        if val is None or str(val).strip() == "-": return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def safe_int(val) -> int:
    try:
        if val is None or str(val).strip() == "-": return 0
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def _normalise_expiry(date_str: str) -> str:
    """Normalises ANY expiry date format NSE uses into YYYY-MM-DD."""
    if not date_str:
        return ""

    s = str(date_str).strip()
    s_lower = s.lower()

    if s_lower in _DATE_CACHE:
        return _DATE_CACHE[s_lower]

    parts = s.split('-')

    # Format 1: DD-Mon-YYYY e.g. '08-May-2026'
    if len(parts) == 3 and not parts[1].isdigit():
        match = re.search(r'(\d{1,2})[- ]([a-z]{3})[a-z]*[- ](\d{2,4})', s_lower)
        if match:
            d = match.group(1).zfill(2)
            m = MONTHS.get(match.group(2), "00")
            y = match.group(3)
            if len(y) == 2: y = "20" + y
            if m != "00":
                res = f"{y}-{m}-{d}"
                _DATE_CACHE[s_lower] = res
                return res

    # Format 2: DD-MM-YYYY e.g. '08-05-2026'
    if len(parts) == 3 and parts[1].isdigit() and len(parts[2]) == 4:
        d, m, y = parts[0].zfill(2), parts[1].zfill(2), parts[2]
        res = f"{y}-{m}-{d}"
        _DATE_CACHE[s_lower] = res
        return res

    # Format 3: already YYYY-MM-DD
    if len(parts) == 3 and len(parts[0]) == 4:
        _DATE_CACHE[s_lower] = s
        return s

    _DATE_CACHE[s_lower] = s
    return s

# Converts a normalised YYYY-MM-DD back to DD-Mon-YYYY for display.
def _display_expiry(norm: str) -> str:

    parts = norm.split('-')
    if len(parts) == 3 and len(parts[0]) == 4:
        y, m, d = parts
        mon = MONTH_NAMES.get(m, m)
        return f"{d}-{mon}-{y}"
    return norm


class OptionsDataStore:
    def __init__(self):
        self._data: Dict[str, Dict[float, Dict[str, deque]]] = {}
        self._underlying_price: float = 0.0
        self._timestamp: str = ""
        self.available_expiries: List[str] = []
        self.current_expiry: str = ""
        self._current_expiry_norm: str = ""
    
    def clear_store(self):
        """Wipes the data store completely when switching between different stock symbols."""
        self._data.clear()
        self._underlying_price = 0.0
        self._timestamp = ""
        self.available_expiries = []
        self.current_expiry = ""
        self._current_expiry_norm = ""

    def update_snapshot(self, raw_data: Dict[str, Any], target_expiry: Optional[str] = None):
        if not raw_data:
            return

        try:
            records  = raw_data.get('records') or {}
            filtered = raw_data.get('filtered') or {}

            self._timestamp        = records.get('timestamp', '')
            self._underlying_price = safe_float(records.get('underlyingValue', 0.0))

            raw_expiries = records.get('expiryDates', [])
            seen_norms   = set()
            self.available_expiries = []
            for d in raw_expiries:
                if not d:
                    continue
                norm = _normalise_expiry(str(d))
                if norm and norm not in seen_norms:
                    seen_norms.add(norm)
                    self.available_expiries.append(_display_expiry(norm))

            if not self.available_expiries:
                return

            if target_expiry:
                target_norm = _normalise_expiry(target_expiry)
                matched_display = next(
                    (d for d in self.available_expiries if _normalise_expiry(d) == target_norm),
                    None
                )
                selected_display = matched_display if matched_display else self.available_expiries[0]
            else:
                selected_display = self.available_expiries[0]

            new_norm = _normalise_expiry(selected_display)

            if new_norm != self._current_expiry_norm:
                self._data.clear()
                self.current_expiry       = selected_display
                self._current_expiry_norm = new_norm

            # ANTI-CLONING FIX: Get the true nearest expiry
            nearest_norm = _normalise_expiry(self.available_expiries[0])

            seen_keys = set()
            all_rows  = []

            for row in (records.get('data') or []):
                if not isinstance(row, dict):
                    continue
                strike = safe_float(row.get('strikePrice', 0))
                
                # Assign blank dates to the true nearest expiry
                key = (strike, nearest_norm)
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_rows.append((row, nearest_norm))

            for row in (filtered.get('data') or []):
                if not isinstance(row, dict):
                    continue
                strike = safe_float(row.get('strikePrice', 0))
                ce     = row.get('CE') or {}
                pe     = row.get('PE') or {}
                raw_exp = (row.get('expiryDate')
                           or row.get('expiryDates')
                           or ce.get('expiryDate')
                           or pe.get('expiryDate')
                           or '')
                
                # Assign blank dates to the true nearest expiry
                exp_norm = _normalise_expiry(str(raw_exp)) if raw_exp else nearest_norm
                
                key = (strike, exp_norm)
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_rows.append((row, exp_norm))

            # Store into rolling deques
            for row, exp_norm in all_rows:
                if exp_norm != self._current_expiry_norm:
                    continue

                strike = safe_float(row.get('strikePrice', 0))
                if strike == 0:
                    continue

                if exp_norm not in self._data:
                    self._data[exp_norm] = {}
                if strike not in self._data[exp_norm]:
                    self._data[exp_norm][strike] = {
                        'CE': deque(maxlen=HISTORY_SIZE),
                        'PE': deque(maxlen=HISTORY_SIZE),
                    }

                for opt_type in ('CE', 'PE'):
                    leg = row.get(opt_type)
                    if leg and isinstance(leg, dict):
                        self._data[exp_norm][strike][opt_type].append({
                            'oi':           safe_int(leg.get('openInterest', 0)),
                            'doi':          safe_int(leg.get('changeinOpenInterest', 0)),
                            'price':        safe_float(leg.get('lastPrice', 0.0)),
                            'volume':       safe_int(leg.get('totalTradedVolume', 0)),
                            'price_change': safe_float(leg.get('change', 0.0)),
                        })

        except Exception as e:
            logging.getLogger("NSE_Store").error(
                f"update_snapshot error: {e}", exc_info=True
            )

    def get_history(self, strike: float, option_type: str) -> List[Dict]:
        return list(
            self._data
            .get(self._current_expiry_norm, {})
            .get(strike, {})
            .get(option_type, [])
        )

    @property
    def current_underlying(self) -> float:
        return self._underlying_price

    @property
    def current_timestamp(self) -> str:
        return self._timestamp

    def get_all_strikes(self) -> List[float]:
        return sorted(self._data.get(self._current_expiry_norm, {}).keys())