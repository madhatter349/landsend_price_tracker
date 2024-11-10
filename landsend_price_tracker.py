import requests
import sqlite3
from datetime import datetime
import json

# API URL for the product
API_URL = "https://www.landsend.com/le-api/pub/product-lookup/product?productId=368990"
DB_NAME = 'landsend_prices.db'

EMAIL_API_URL = "https://www.cinotify.cc/api/notify"  # Replace with your email API endpoint
EMAIL_RECIPIENT = "your_email@example.com"  # Replace with your recipient email

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
        first_seen TEXT,
        last_seen TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_time TEXT
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
        return []

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    current_time = datetime.now().isoformat()

    new_posts = []

    for style in data.get("styles", []):
        if style["styleNumber"] == "531211":  # Filter for specific styleNumber
            price = style["price"]
            cursor.execute('SELECT id FROM prices WHERE styleNumber = ? AND sizeCode = ? AND colorCode = ?',
                           (style["styleNumber"], style["sizeCode"], style["colorCode"]))
            result = cursor.fetchone()
            if result is None:
                # New entry
                cursor.execute('''
                INSERT INTO prices (styleNumber, sizeCode, colorCode, currentPrice, originalPrice, promotionalPrice, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (style["styleNumber"], style["sizeCode"], style["colorCode"],
                      price["currentPrice"], price["originalPrice"], price["promotionalPrice"], current_time, current_time))
                new_posts.append(style)
            else:
                # Update existing entry
                cursor.execute('UPDATE prices SET last_seen = ?, promotionalPrice = ? WHERE id = ?',
                               (current_time, price["promotionalPrice"], result[0]))

    cursor.execute('INSERT INTO runs (run_time) VALUES (?)', (current_time,))
    conn.commit()
    conn.close()
    return new_posts

def get_removed_posts():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT run_time FROM runs ORDER BY id DESC LIMIT 1 OFFSET 1')
    result = cursor.fetchone()
    if not result:
        return []  # No previous runs to compare

    previous_run_time = result[0]
    cursor.execute('''
    SELECT styleNumber, sizeCode, colorCode, currentPrice, originalPrice, promotionalPrice
    FROM prices
    WHERE last_seen = ? AND last_seen < (SELECT MAX(run_time) FROM runs)
    ''', (previous_run_time,))
    removed_posts = [dict(zip(['styleNumber', 'sizeCode', 'colorCode', 'currentPrice', 'originalPrice', 'promotionalPrice'], row)) for row in cursor.fetchall()]
    conn.close()
    return removed_posts

def send_email(new_posts):
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    for post in new_posts:
        body_content = f"""
        <h2>New Promotional Price Detected</h2>
        <p>Details:</p>
        <ul>
            <li>Style Number: {post['styleNumber']}</li>
            <li>Size: {post['sizeCode']}</li>
            <li>Color: {post['colorCode']}</li>
            <li>Promotional Price: ${post['price']['promotionalPrice']}</li>
        </ul>
        """

        subject_title = f"New Price Alert: Style {post['styleNumber']}"

        data = {
            'to': EMAIL_RECIPIENT,
            'subject': subject_title,
            'body': body_content,
            'type': 'text/html'
        }

        response = requests.post(EMAIL_API_URL, headers=headers, data=data)
        log_debug(f"Email status: {response.status_code}, response: {response.text}")

def main():
    log_debug("Script started")
    init_db()

    data = fetch_product_data()
    new_posts = parse_and_store_data(data)
    removed_posts = get_removed_posts()

    if new_posts:
        send_email(new_posts)
        log_debug(f"Sent email for {len(new_posts)} new posts.")
    else:
        log_debug("No new promotional prices.")

    if removed_posts:
        log_debug(f"{len(removed_posts)} posts no longer available.")

    log_debug("Script finished")

if __name__ == "__main__":
    main()
