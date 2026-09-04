# **Contributing to the Trading Terminal**

Thank you for your interest in contributing! We are actively building a high-performance, keyboard-first terminal interface for market data, and we are eager to welcome talented individuals to the project. 

To keep our development focused and our architecture lean, we'll operate with a highly targeted roadmap. 

## Current Priorities (What We Are Looking For)
At this moment, we are exclusively seeking contributions to solve two specific challenges:

### 1. Bug Fix: Expiry Filter Rendering Issue
* **The Problem:** The expiry filter is currently broken. When a user navigates to a specific options expiry date, the data table renders completely blank and no data is visible. 
* **The Goal:** Debug the data routing between the fetcher, the store, and the UI table to ensure the options chain renders correctly when a specific expiry is selected.

## Important Note on Scope
To maintain the stability and specific architectural vision of this project, **we are currently ONLY accepting Pull Requests (PRs) that address the two priorities listed above.** Please do not submit PRs for UI overhauls, new color schemes, or heavy structural changes at this time. 

**The Exception:** If you discover a critical, application-crashing bug we will absolutely accept an urgent hotfix. For anything else, please open an Issue first to discuss it before writing any code.

## How to Contribute
1. **Fork the repository** and clone it to your local machine.
2. **Create a branch** specifically for the issue you are tackling (e.g., `git checkout -b fix/expiry-filter-blank`).
3. **Write your code**, ensuring it adheres to the existing data-first, lightweight architecture.
4. **Test your changes** thoroughly to ensure the terminal remains non-blocking and responsive.
5. **Submit a Pull Request** with a clear explanation of how you solved the problem.

We are excited to see your solutions!
