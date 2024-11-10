import requests
import sqlite3
import json
from datetime import datetime
import os

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
        return response.json()
    except Exception as e:
        log_debug(f"Error fetching product data: {e}")
        return None

def update_database(data):
    if not data:
        return [], []

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    current_time = datetime.now().isoformat()
    new_posts = []
    updated_posts = []

    for style in data.get("styles", []):
        if style["styleNumber"] == "531211":
            price = style["price"]
            cursor.execute('SELECT id, currentPrice, promotionalPrice FROM prices WHERE styleNumber = ? AND sizeCode = ? AND colorCode = ?',
                           (style["styleNumber"], style["sizeCode"], style["colorCode"]))
            result = cursor.fetchone()
            
            if result is None:
                # New entry
                cursor.execute('''
                INSERT INTO prices (styleNumber, sizeCode, colorCode, currentPrice, originalPrice, promotionalPrice, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (style["styleNumber"], style["sizeCode"], style["colorCode"], price["currentPrice"], price["originalPrice"], price["promotionalPrice"], current_time, current_time))
                new_posts.append(style)
            else:
                # Update only if the price changed
                if result[1] != price["currentPrice"] or result[2] != price["promotionalPrice"]:
                    updated_posts.append({
                        "styleNumber": style["styleNumber"],
                        "sizeCode": style["sizeCode"],
                        "colorCode": style["colorCode"],
                        "oldPrice": result[2],
                        "newPromotionalPrice": price["promotionalPrice"]
                    })
                cursor.execute('UPDATE prices SET last_seen = ?, currentPrice = ?, promotionalPrice = ? WHERE id = ?',
                               (current_time, price["currentPrice"], price["promotionalPrice"], result[0]))

    cursor.execute('INSERT INTO runs (run_time) VALUES (?)', (current_time,))
    conn.commit()
    conn.close()

    return new_posts, updated_posts

def get_removed_posts():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT run_time FROM runs ORDER BY id DESC LIMIT 1 OFFSET 1')
    previous_run_time = cursor.fetchone()
    
    if not previous_run_time:
        return []

    cursor.execute('''
    SELECT styleNumber, sizeCode, colorCode, currentPrice, promotionalPrice
    FROM prices
    WHERE last_seen = ? AND last_seen < (SELECT MAX(run_time) FROM runs)
    ''', (previous_run_time[0],))
    
    removed_posts = [dict(zip(['styleNumber', 'sizeCode', 'colorCode', 'currentPrice', 'promotionalPrice'], row)) for row in cursor.fetchall()]
    conn.close()
    
    return removed_posts

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
            <li>Old Promotional Price: ${post['oldPrice']}</li>
            <li>New Promotional Price: ${post['newPromotionalPrice']}</li>
        </ul>
        """
        data = {
            'to': 'Madhatter349@gmail.com',
            'subject': f"Price Change: Style {post['styleNumber']}",
            'body': body_content,
            'type': 'text/html'
        }
        response = requests.post("https://www.cinotify.cc/api/notify", headers=headers, data=data)
        log_debug(f"Email response: {response.status_code}, {response.text}")

def main():
    log_debug("Script started")
    init_db()
    
    data = fetch_product_data()
    new_posts, updated_posts = update_database(data)
    removed_posts = get_removed_posts()
    
    # Save comparison results to JSON
    comparison_results = {
        'new_posts': new_posts,
        'updated_posts': updated_posts,
        'removed_posts': removed_posts
    }
    
    with open('comparison_result.json', 'w') as f:
        json.dump(comparison_results, f, indent=2)
    log_debug("Comparison results saved to comparison_result.json")
    
    log_debug(f"New posts: {len(new_posts)}, Updated posts: {len(updated_posts)}, Removed posts: {len(removed_posts)}")
    
    if updated_posts:
        send_email(updated_posts)
    
    log_debug("Script finished")

if __name__ == "__main__":
    main()
