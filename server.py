import json
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
MENU = [
    {"id": "ramen", "name": "Truffle Ramen", "price": 89000, "emoji": "🍜", "description": "Yumshoq tuxum, shiitake qo‘ziqorini, truffle yog‘i va uy noodlelari.", "rating": 4.9},
    {"id": "gyoza", "name": "Gyoza Mix", "price": 45000, "emoji": "🥟", "description": "6 dona qarsildoq gyoza.", "rating": 4.7},
    {"id": "chicken", "name": "Butter Chicken", "price": 72000, "emoji": "🍛", "description": "O‘rtacha achchiq, qaymoqli sousdagi tovuq.", "rating": 4.8},
    {"id": "matcha", "name": "Matcha Latte", "price": 29000, "emoji": "🍵", "description": "Muzli matcha latte.", "rating": 4.6},
]
cart = {}
orders = []
RESPONSES = {
    "yengil": "Ajoyib tanlov. Sizga bug‘da pishirilgan sabzavotlar va kunjutli tofu salatini tavsiya qilaman. Yengil, ammo mazali!",
    "foydali": "Ajoyib tanlov. Sizga bug‘da pishirilgan sabzavotlar va kunjutli tofu salatini tavsiya qilaman. Yengil, ammo mazali!",
    "issiq": "Unda Truffle Ramen aynan siz uchun. U iliq, to‘yimli va chefimizning bugungi maxsus taomi.",
    "to‘yimli": "Unda Truffle Ramen aynan siz uchun. U iliq, to‘yimli va chefimizning bugungi maxsus taomi.",
    "shirin": "Bugun yangi tayyorlangan matcha cheesecake bor. Shirinligi me’yorida, yoniga issiq choy juda mos tushadi.",
}

class BotHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health": return self.send_json({"ok": True, "service": "Ta'mBot API"})
        if path == "/api/menu": return self.send_json({"items": MENU})
        if path == "/api/cart": return self.send_json(self.cart_data())
        if path == "/api/orders": return self.send_json({"orders": orders})
        self.serve_file(path)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_body()
            if path == "/api/chat": return self.chat(payload.get("message", ""))
            if path == "/api/cart": return self.add_to_cart(payload.get("item_id"))
            if path == "/api/orders": return self.create_order(payload)
            self.send_json({"error": "Endpoint topilmadi"}, 404)
        except (ValueError, KeyError, TypeError) as error:
            self.send_json({"error": f"So‘rov noto‘g‘ri: {error}"}, 400)

    def chat(self, message):
        text = message.strip().lower()
        answer = next((value for key, value in RESPONSES.items() if key in text), "Tushundim. Menyudan sizga eng mos variantlarni tanlayapman. Taomda allergiya yoki cheklovingiz bormi?")
        self.send_json({"reply": answer, "suggestion": MENU[0]})

    def add_to_cart(self, item_id):
        item = next((menu_item for menu_item in MENU if menu_item["id"] == item_id), None)
        if not item: return self.send_json({"error": "Taom topilmadi"}, 404)
        cart[item_id] = cart.get(item_id, 0) + 1
        self.send_json(self.cart_data(), 201)

    def cart_data(self):
        items = [{**next(item for item in MENU if item["id"] == item_id), "quantity": quantity} for item_id, quantity in cart.items()]
        return {"items": items, "total": sum(item["price"] * item["quantity"] for item in items)}

    def create_order(self, payload):
        current_cart = self.cart_data()
        if not current_cart["items"]: return self.send_json({"error": "Savat bo‘sh"}, 400)
        order = {"id": f"TB-{random.randint(1000, 9999)}", "items": current_cart["items"], "total": current_cart["total"], "status": "Qabul qilindi", "customer": payload.get("customer", {})}
        orders.append(order)
        cart.clear()
        self.send_json(order, 201)

    def serve_file(self, path):
        file_path = (ROOT / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
        if ROOT not in file_path.parents or not file_path.is_file(): return self.send_json({"error": "Sahifa topilmadi"}, 404)
        content_type = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    print("Ta'mBot backend: http://127.0.0.1:4173")
    ThreadingHTTPServer(("127.0.0.1", 4173), BotHandler).serve_forever()