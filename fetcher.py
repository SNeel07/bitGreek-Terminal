import logging
import time
import requests
from typing import Optional
from pathlib import Path

# 1. Define the safe user directory for logs and downloads
user_dir = Path.home() / ".nse_terminal"
user_dir.mkdir(parents=True, exist_ok=True)
log_path = user_dir / "fetcher.log"

# 2. Configure logging to use the safe absolute path
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(str(log_path))]
)
logger = logging.getLogger("NSE_Fetcher")

class NSEDataFetcher:
    """
    Singleton class to manage a persistent connection to the NSE servers.
    """
    _instance = None
    session = None
    headers = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NSEDataFetcher, cls).__new__(cls)
            logger.info("Initializing persistent NSE Session via Requests...")
            
            cls.session = requests.Session()
            # Standard headers without Accept-Encoding to prevent binary Brotli data
            cls.headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.nseindia.com/option-chain",
            }
        return cls._instance

    def _get_cookies(self):
        """Hit the homepage once to establish a valid session cookie."""
        try:
            self.session.get("https://www.nseindia.com", headers=self.headers, timeout=5)
        except Exception as e:
            logger.error(f"Failed to fetch initial cookies: {e}")

    def get_option_chain(self, symbol: str = "NIFTY", target_expiry: str = None, retries: int = 3) -> Optional[dict]:
        """
        Fetches the option chain dynamically using the v3 endpoint and specific expiry.
        """
        for attempt in range(retries):
            try:
                logger.info(f"Fetching Option Chain for {symbol} (Attempt {attempt + 1}/{retries})...")
                self._get_cookies()

                # Fetch Contract Info to get the list of all available expiry dates
                info_url = f"https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol}"
                expiries = []
                info_response = self.session.get(info_url, headers=self.headers, timeout=5)
                
                if info_response.status_code == 200:
                    expiries = info_response.json().get("expiryDates", [])
                
                # Determine which expiry to fetch (default to the closest one if None)
                if not target_expiry and expiries:
                    target_expiry = expiries[0]
                elif not target_expiry:
                    logger.warning("No target expiry provided and failed to fetch expiries list.")
                    return None

                logger.info(f"Target Expiry Selected: {target_expiry}")

                # Fetch the exact v3 data for that specific date
                symbol_type = "Indices" if symbol in ("NIFTY", "BANKNIFTY") else "Equities"
                chain_url = f"https://www.nseindia.com/api/option-chain-v3?type={symbol_type}&symbol={symbol}&expiry={target_expiry}"
                chain_response = self.session.get(chain_url, headers=self.headers, timeout=5)
                
                if chain_response.status_code == 200:
                    data = chain_response.json()

                    # Safely inject the expiry list into the payload so your store.py can read it
                    if "records" not in data:
                        data["records"] = {}
                    data["records"]["expiryDates"] = expiries

                    return data
                else:
                    logger.warning(f"Failed to fetch chain. Status Code: {chain_response.status_code}")

            except requests.exceptions.JSONDecodeError:
                logger.error("JSONDecodeError: Server returned non-JSON data (possibly blocked).")
            except Exception as e:
                logger.error(f"Network or parsing error during fetch: {e}")
            
            # Exponential backoff
            time.sleep(2 ** (attempt + 1))
            
        logger.error(f"Failed to fetch Option Chain for {symbol} after {retries} attempts.")
        return None

# Local execution block
if __name__ == "__main__":
    fetcher = NSEDataFetcher()
    
    # Singleton validation
    fetcher_duplicate = NSEDataFetcher()
    assert fetcher is fetcher_duplicate, "Singleton implementation failed!"
    logger.info("Singleton verification passed.")

    # Execution
    logger.info("Initiating test fetch sequence...")
    test_data = fetcher.get_option_chain("NIFTY")
    
    if test_data:
        logger.info("Successfully fetched data!")
        if isinstance(test_data, dict):
            print(f"Top-level keys: {list(test_data.keys())}")
            if 'records' in test_data:
                 print(f"Records keys: {list(test_data['records'].keys())}")
                 print(f"Expiries found: {test_data['records'].get('expiryDates', [])[:3]}...")
        else:
            print("Data is not a dictionary. Raw output:")
            print(test_data)
    else:
        logger.error("Failed to retrieve data on initial test.")