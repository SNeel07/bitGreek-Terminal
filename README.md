# **NSE OPTIONS TERMINAL**

The NSE Options Terminal is a light-weight market analysis tool designed to visualize and simplify the NSE's flagship index NIFTY50 option chain. Instead of displaying raw options chain data exactly as received from NSE, the terminal processes, organizes and highlights important metrics so traders can quickly understand market positioning, option activity and potential market direction.

* [Installation](#installation)
* [Why a Terminal](#why-a-terminal)
* [Contributions](#how-can-you-help-us)
* [Tech Stack & Architecture](#tech-stack-and-architecture)
* [Everything about Options Market](#new-to-options-market)
* [Special Note](#special-note)

## **Installation**
For those who want to download the ready-made tool [click here](https://bitgreekterminal.netlify.app/) for the latest version.<br>
**Note:** When trying to run the app for the first time, you will most certainly get a message from Windows Defender. There's nothing to worry about!<br>
Just click on "**More info**" and then "**Run anyway**"

## **Why a Terminal?**
Traditional option chain pages expose large amounts of raw market data that can be difficult to interpret quickly.
This terminal acts as an analysis layer on top of NSE data by:
<p>-Fetching live option chain data directly from NSE.</p>
<p>-Organizing important metrics into a cleaner layout.</p>
<p>-Highlighting market positioning.</p>
<p>-Tracking Open Interest changes.</p>
<p>-Detecting option trends automatically.</p>
<p>-Providing faster visual interpretation of market activity.</p>

The goal is not to replace NSE data, but to transform raw option chain information into actionable insights that can be understood by beginners, active traders and professional market participants alike.

## **How can you help us?**
This project is open for contributions. You can help us by contributing to the features mentioned in the [CONTRIBUTION.md](CONTRIBUTION.md)
<br>
The [CONTRIBUTION.md](CONTRIBUTION.md) will be updated as we move on with the fixes and new features.<br>
To understand how the tool works under the hood please go through the [Tech Stack](#tech-stack-and-architecture) section

## **Tech Stack and Architecture**
**Language**: Python 3.11+ — chosen for its rich ecosystem of financial and terminal UI libraries.

### Core Libraries

| Library | Version | Purpose |
|---|---|---|
| [Textual](https://github.com/Textualize/textual) | ≥0.52 | Terminal UI framework — screens, widgets, layout, keybindings |
| [Rich](https://github.com/Textualize/rich) | ≥13.0 | Text styling, coloured cells, and inline markup inside Textual |
| [nse](https://github.com/BennyThadikaran/NseIndiaApi) | ≥2.0 | NSE session management, cookie handling, and option chain fetching |

### How Data is Fetched?

NSE does not provide a public REST API. Their website uses session-based authentication — every request must carry a valid cookie obtained by first hitting the NSE homepage.

The `nse` library (by Benny Thadikaran) handles this automatically:
1. On startup, it hits `nseindia.com` to warm up a session and store cookies to disk
2. Subsequent calls to `optionChain("NIFTY")` attach these cookies to the API request
3. Cookies expire every ~5–8 minutes and are automatically refreshed

The raw response is a JSON object with two blocks:
- `records` — contains `underlyingValue`, `timestamp`, `expiryDates`, and `data` (130 strikes, `expiryDate=None`)
- `filtered` — contains the same strikes but with `expiryDate` populated in `DD-MM-YYYY` format

We use `filtered.data` as the primary source for strike-level data (since it has expiry dates), and `records.data` as a fallback for additional strikes. Deduplication by `(strikePrice, expiryDate)` prevents double-counting.

### How OI Classification Works?

Each fetch stores a snapshot of every strike's OI and price into a rolling deque (size 5) inside `store.py`. The key insight is that NSE already computes the intraday delta for us:

- `changeinOpenInterest` — net OI change since **previous day's close** (resets to 0 at 9:15 AM)
- `change` — net price change since **previous day's close**

This means a single snapshot already carries the full intraday picture. `calculator.py` reads these two fields from the latest entry and classifies each strike into one of four quadrants:

| Classification | OI | Price | Market Interpretation |
|---|---|---|---|
| Long Buildup | ↑ | ↑ | Fresh longs entering — Strong bullish |
| Short Buildup | ↑ | ↓ | Fresh shorts entering — Strong bearish |
| Long Unwinding | ↓ | ↓ | Longs exiting their positions — Moderate bearish |
| Short Covering | ↓ | ↑ | Shorts covering their positions — Moderate bullish |

Classifications reset naturally at market open each day because NSE resets `changeinOpenInterest` to 0 at 9:15 AM.

### Data Flow (End to End)
NSE API (via nse library)
<br>
▼ fetcher.py — singleton session, retry logic, exponential backoff
<br></br>
▼ store.py — parses raw JSON, normalises expiry dates, stores
rolling deque of {oi, doi, price, price_change, volume}
per strike per option type (CE/PE)
<br></br>
▼ calculator.py — reads latest snapshot, classifies each strike
using NSE's intraday delta fields
<br></br>
▼ app.py — Textual app, background worker thread polls every
N seconds (user-configurable), pushes updates to UI
<br></br>
▼ widgets/ — Textual widgets render the classified data<br>
&emsp;&emsp;&emsp;&emsp;&emsp;├── header.py — PCR, total CE/PE OI, spot price, market status badge<br>
&emsp;&emsp;&emsp;&emsp;&emsp;├── oi_table.py — symmetrical CE | Strike | PE DataTable<br>
&emsp;&emsp;&emsp;&emsp;&emsp;├── sidebar.py — quick links panel (persisted to ~/.nse_terminal/links.json)<br>
&emsp;&emsp;&emsp;&emsp;&emsp;├── expiry_modal.py — expiry date selector<br>
&emsp;&emsp;&emsp;&emsp;&emsp;├── switcher.py — terminal switcher (NSE / BSE)<br>
&emsp;&emsp;&emsp;&emsp;&emsp;└── interval_modal.py — poll interval selector (1–10 minutes)<br>

### Threading Model

The app runs a **single persistent background thread** (`update_data_loop`) using Textual's `@work(thread=True)` decorator. A `threading.Event` controls the poll interval — the thread sleeps for N seconds but can be woken early by:
- Pressing `r` (force refresh)
- Changing the poll interval via `i`

This guarantees exactly one fetch loop is ever running — no overlapping workers, no race conditions.

### Persistence

User data that survives app restarts:
- **Quick links** — stored in `~/.nse_terminal/links.json`
- **NSE session cookies** — stored in the project directory by the `nse` library, avoiding a full re-authentication on every startup

### Market Hours & Holidays

The terminal is aware of:
- **Weekends** — Saturday and Sunday are always closed
- **NSE trading holidays** — a hardcoded set of all 17 official NSE holidays for the current year (see `NSE_HOLIDAYS_2026` in `app.py`)
- **Trading hours** — 09:15 to 15:30 IST

Outside market hours the terminal continues to display the last known data snapshot. The header badge switches between &emsp; <span style="color: #26ed65;"><strong>●</strong></span> `Market Open` &emsp;and &emsp;<span style="color: #ff4d4d;"><strong>●</strong></span> `Market Closed` in real time.

## **New to Options Market?**
If you are new to option chains and want to have a basic over view of those things work there, please go through the [OPTION_CHAIN.md](OPTION_CHAIN.md)

### **Special Note**

This terminal was built with one goal in mind — to give traders a faster, cleaner and more transparent view of the options market, without the noise of a browser or the lag of a paid platform.

We believe powerful trading tools should not be locked behind expensive subscriptions or cluttered interfaces. This project is our first step toward that belief.

**It is not finished. It was never meant to be finished by us alone.**

The BSE terminal is waiting to be unlocked and many more are on the roadmap.

Every line of this codebase is open. Every architectural decision is documented. Every known limitation is written down honestly in [CONTRIBUTION.md](CONTRIBUTION.md) — not hidden, not glossed over.

If you are a developer who trades, or a trader who codes, or simply someone enthusiastic, who believes that open source financial tooling matters — **this project is for you.**

Fork it. Break it. Improve it. Build something on top of it that we could not imagine.

**The market opens at 9:15. So do we.**

<span style="color: #ff4d4d;"><strong>**Disclaimer:**</strong></span><br>
This software is intended for educational and analytical purposes only.<br>
It does not provide investment advice, trading recommendations or guarantees future market performance. Users are responsible for their own trading and investment decisions.
