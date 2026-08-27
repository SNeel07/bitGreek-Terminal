import logging
import time
from typing import Optional
from pathlib import Path
from nse import NSE

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
    _client: Optional[NSE] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NSEDataFetcher, cls).__new__(cls)
            logger.info("Initializing persistent NSE Session...")
            
            # 3. Update the download folder so the NSE library doesn't crash in Program Files
            cls._client = NSE(download_folder=str(user_dir)) 
        return cls._instance

    def get_option_chain(self, symbol: str = "NIFTY", retries: int = 3) -> Optional[dict]:
        """
        Fetches the latest option chain. Uses dynamic attribute checking to ensure 
        we catch the correct method name from the external package.
        """
        for attempt in range(retries):
            try:
                logger.info(f"Fetching Option Chain for {symbol} (Attempt {attempt + 1}/{retries})...")
                
                # Dynamic method execution to bypass package documentation gaps
                if hasattr(self._client, 'optionChain'):
                    data = self._client.optionChain(symbol)
                elif hasattr(self._client, 'getOptionChain'):
                    data = self._client.getOptionChain(symbol)
                else:
                    # If the method is named something else, print all available methods instantly
                    available_methods = [m for m in dir(self._client) if not m.startswith('_')]
                    logger.error(f"Option chain method missing! Available methods are: {available_methods}")
                    return None
                
                if data:
                    return data
                else:
                    logger.warning("Received empty data from NSE.")
                    
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
        else:
            print("Data is not a dictionary. Raw output:")
            print(test_data)
    else:
        logger.error("Failed to retrieve data on initial test.")