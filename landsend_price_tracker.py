import requests
import sqlite3
from datetime import datetime
import json

# API URL
API_URL = "https://www.landsend.com/le-api/pub/product-lookup/product?productId=368990"
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
        data = response.json()
        log_debug(f"API Response: {json.dumps(data, indent=2)}")
        return data.get("productDetail", {}).get("skus", [])
    except Exception as e:
        log_debug(f"Error fetching product data: {e}")
        return None

def update_database(skus):
    target_sku = next((sku for sku in skus if sku["styleNumber"] == 531211 and sku["sizeCode"] == "M" and sku["colorCode"] == "A6J"), None)
    
    if not target_sku:
        log_debug("Target SKU not found.")
        return [], []

    price = target_sku["price"]
    current_price = price.get("currentPrice")
    original_price = price.get("originalPrice")
    promotional_price = price.get("promotionalPrice", current_price)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    current_time = datetime.now().isoformat()
    new_posts = []
    updated_posts = []

    cursor.execute('SELECT id, promotionalPrice FROM prices WHERE styleNumber = ? AND sizeCode = ? AND colorCode = ?',
                   (531211, "M", "A6J"))
    result = cursor.fetchone()
    
    if result is None:
        cursor.execute('''
        INSERT INTO prices (styleNumber, sizeCode, colorCode, currentPrice, originalPrice, promotionalPrice, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (531211, "M", "A6J", current_price, original_price, promotional_price, current_time, current_time))
        new_posts.append(target_sku)
    else:
        if result[1] != promotional_price:
            updated_posts.append({
                "styleNumber": 531211,
                "sizeCode": "M",
                "colorCode": "A6J",
                "oldPromotionalPrice": result[1],
                "newPromotionalPrice": promotional_price
            })
        cursor.execute('UPDATE prices SET last_seen = ?, currentPrice = ?, promotionalPrice = ? WHERE id = ?',
                       (current_time, current_price, promotional_price, result[0]))

    cursor.execute('INSERT INTO runs (run_time) VALUES (?)', (current_time,))
    conn.commit()
    conn.close()

    return new_posts, updated_posts

def send_email(updated_posts):
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    for post in updated_posts:
        body_content = f"""
        <h2>Price Change Detected</h2>
        <p>Details:</p>
        <ul>
            <li>Style Number: {post['styleNumber']}</li>
            <li>Size: {post['sizeCode']}</li>
            <li>Color: {post['colorCode']}</li>
            <li>Old Promotional Price: ${post['oldPromotionalPrice']}</li>
            <li>New Promotional Price: ${post['newPromotionalPrice']}</li>
        </ul>
        """
        data = {
            'to': 'madhatter349@gmail.com',
            'subject': f"Price Change: Style {post['styleNumber']}",
            'body': body_content,
            'type': 'text/html'
        }
        response = requests.post("https://www.cinotify.cc/api/notify", headers=headers, data=data)
        log_debug(f"Email response: {response.status_code}, {response.text}")

def main():
    log_debug("Script started")
    init_db()
    
    skus = fetch_product_data()
    new_posts, updated_posts = update_database(skus)
    
    if updated_posts:
        send_email(updated_posts)
    
    log_debug("Script finished")

if __name__ == "__main__":
    main()
