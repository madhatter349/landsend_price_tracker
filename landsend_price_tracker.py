import requests
import sqlite3
from datetime import datetime
import json

# API URL for the product
API_URL = "https://www.landsend.com/le-api/pub/product-lookup/product?productId=368990"

# Database setup
DB_NAME = 'landsend_prices.db'

def log_debug(message):
    with open('debug.log', 'a') as f:
        f.write(f"{datetime.now()}: {message}\n")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        styleNumber TEXT,
        sizeCode TEXT,
        colorCode TEXT,
        currentPrice REAL,
        originalPrice REAL,
        promotionalPrice REAL,
        timestamp TEXT
    )
    ''')
    conn.commit()
    conn.close()

def fetch_product_data():
    try:
        response = requests.get(API_URL)
        if response.status_code != 200:
            log_debug(f"Failed to fetch data: {response.status_code}")
            return None
        return response.json()
    except Exception as e:
        log_debug(f"Error fetching product data: {e}")
        return None

def parse_and_store_data(data):
    if not data:
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for style in data.get("styles", []):
        if style["styleNumber"] == "531211":
            price = style["price"]
            cursor.execute('''
            INSERT INTO prices (styleNumber, sizeCode, colorCode, currentPrice, originalPrice, promotionalPrice, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                style["styleNumber"],
                style["sizeCode"],
                style["colorCode"],
                price["currentPrice"],
                price["originalPrice"],
                price["promotionalPrice"],
                datetime.now().isoformat()
            ))
            log_debug(f"Stored promotional price: {price['promotionalPrice']}")
    
    conn.commit()
    conn.close()

def main():
    log_debug("Script started")
    init_db()
    
    data = fetch_product_data()
    parse_and_store_data(data)
    
    log_debug("Script finished")

if __name__ == "__main__":
    main()
