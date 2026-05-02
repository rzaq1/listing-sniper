name: Listing Sniper

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  run-sniper:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests tzdata

      - name: Restore seen listings cache
        uses: actions/cache@v4
        with:
          path: seen_listings.json
          key: seen-listings-cache
          restore-keys: seen-listings-cache

      - name: Run sniper
        run: python sniper.py

      - name: Save seen listings cache
        uses: actions/cache/save@v4
        if: always()
        with:
          path: seen_listings.json
          key: seen-listings-cache-${{ github.run_id }}
