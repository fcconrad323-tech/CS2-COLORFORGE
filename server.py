import os, re, time, threading
import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "CS2-Colorforge/2.0 (+personal loadout tool)"})
CACHE = {}
LOCK = threading.Lock()
CACHE_TTL = 300

def cached(key, ttl, loader):
    now = time.time()
    with LOCK:
        hit = CACHE.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = loader()
    with LOCK:
        CACHE[key] = (now, value)
    return value

def usd_number(value):
    if value is None:
        return None
    s = re.sub(r"[^0-9.]", "", str(value))
    try:
        n = float(s)
        return n if n > 0 else None
    except ValueError:
        return None

def fetch_catalogue():
    url = "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/en/skins.json"
    r = SESSION.get(url, timeout=25)
    r.raise_for_status()
    data = r.json()
    return [{"name": x.get("name"), "image": x.get("image")}
            for x in data if x.get("name") and x.get("image")]

@app.get("/api/catalogue")
def catalogue():
    try:
        return jsonify(cached("catalogue", 3600, fetch_catalogue))
    except Exception as e:
        return jsonify({"error": "Skin catalogue could not be loaded", "detail": str(e)}), 502

def skinport_rows():
    def load():
        url = "https://api.skinport.com/v1/items"
        params = {"app_id": 730, "currency": "USD", "tradable": 1}
        headers = {"Accept-Encoding": "br"}
        r = SESSION.get(url, params=params, headers=headers, timeout=35)
        r.raise_for_status()
        return r.json()
    return cached("skinport_usd_items", 300, load)

def price_skinport(full_name):
    try:
        rows = skinport_rows()
        prefix = full_name.lower() + " ("
        matches = [x for x in rows
                   if str(x.get("market_hash_name","")).lower().startswith(prefix)
                   and isinstance(x.get("min_price"), (int,float))
                   and x.get("min_price", 0) > 0
                   and x.get("quantity", 0) > 0]
        if not matches:
            return None
        matches.sort(key=lambda x: x["min_price"])
        x = matches[0]
        wear = re.search(r"\(([^)]+)\)", x["market_hash_name"])
        return {"usd": float(x["min_price"]), "wear": wear.group(1) if wear else "",
                "source": "Skinport", "url": x.get("item_page")}
    except Exception as e:
        app.logger.warning("Skinport lookup failed: %s", e)
        return None

def price_csfloat(full_name):
    try:
        params = {"limit": 10, "sort_by": "lowest_price", "type": "buy_now",
                  "market_hash_name": full_name}
        r = SESSION.get("https://csfloat.com/api/v1/listings", params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        rows = data if isinstance(data, list) else data.get("data", [])
        rows = [x for x in rows if x.get("state") == "listed" and
                isinstance(x.get("price"), (int,float)) and x["price"] > 0]
        if not rows:
            return None
        rows.sort(key=lambda x: x["price"])
        x = rows[0]
        item = x.get("item") or {}
        return {"usd": x["price"] / 100, "wear": item.get("wear_name", ""),
                "source": "CSFloat",
                "url": "https://csfloat.com/search?market_hash_name=" + requests.utils.quote(full_name)}
    except Exception as e:
        app.logger.warning("CSFloat lookup failed: %s", e)
        return None

def price_steam(full_name):
    """Return the cheapest live Steam listing across all standard wear grades."""
    wear_grades = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
    found = []
    for wear in wear_grades:
        market_name = f"{full_name} ({wear})"
        try:
            params = {"appid": 730, "currency": 1, "market_hash_name": market_name}
            r = SESSION.get("https://steamcommunity.com/market/priceoverview/", params=params, timeout=12)
            r.raise_for_status()
            data = r.json()
            if not data.get("success"):
                continue
            value = usd_number(data.get("lowest_price"))
            if value is None:
                continue
            found.append({"usd": value, "wear": wear, "source": "Steam",
                          "url": "https://steamcommunity.com/market/listings/730/" +
                                 requests.utils.quote(market_name, safe="")})
        except Exception as e:
            app.logger.warning("Steam lookup failed for %s: %s", market_name, e)
    return min(found, key=lambda x: x["usd"]) if found else None

@app.get("/api/price")
def price():
    weapon = request.args.get("weapon", "").strip()
    skin = request.args.get("skin", "").strip()
    market = request.args.get("market", "all")
    if not weapon or not skin or market not in ("all", "steam", "third"):
        return jsonify({"error": "Invalid request"}), 400
    full_name = f"{weapon} | {skin}"
    checks = []
    if market in ("all", "third"):
        checks.extend([price_skinport(full_name), price_csfloat(full_name)])
    if market in ("all", "steam"):
        checks.append(price_steam(full_name))
    found = [x for x in checks if x]
    found.sort(key=lambda x: x["usd"])
    return jsonify({"price": found[0] if found else None, "prices": found,
                    "checked": ["Steam", "Skinport", "CSFloat"] if market == "all"
                               else (["Steam"] if market == "steam" else ["Skinport", "CSFloat"])})

@app.get("/api/rates")
def rates():
    def load():
        r = SESSION.get("https://open.er-api.com/v6/latest/USD", timeout=15)
        r.raise_for_status()
        d = r.json()
        if d.get("result") != "success":
            raise RuntimeError("Exchange rate feed returned an error")
        return {"NAD": d["rates"]["NAD"], "ZAR": d["rates"]["ZAR"]}
    try:
        return jsonify(cached("usd_rates", 3600, load))
    except Exception as e:
        return jsonify({"error": "Currency conversion unavailable", "detail": str(e)}), 502

@app.get("/")
def home():
    return send_from_directory(".", "index.html")

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "CS2 COLORFORGE backend"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
