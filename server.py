import os
import hashlib
import hmac
import random
from flask import Flask, request, jsonify
import requests
from PIL import Image, ImageDraw

# ===== ENV VARIABLES (SET IN RENDER) =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

# store active bets in memory
ACTIVE_BETS = {}

# ===== PROVABLY FAIR CORE (REAL) =====
def compute_mines(server_seed, client_seed, nonce, mines):
    # verify hash
    server_hash = hashlib.sha256(server_seed.encode()).hexdigest()

    msg = f"{client_seed}:{nonce}".encode()
    key = server_seed.encode()
    h = hmac.new(key, msg, hashlib.sha256).hexdigest()

    rng = random.Random(int(h[:16], 16))
    tiles = list(range(25))
    rng.shuffle(tiles)

    mine_tiles = set(tiles[:mines])
    safe_tiles = set(tiles[mines:])

    return server_hash, mine_tiles, safe_tiles


# ===== IMAGE GENERATOR =====
def generate_image(mines):
    img = Image.new("RGB", (500, 500), "#0f172a")
    d = ImageDraw.Draw(img)

    for i in range(25):
        x = (i % 5) * 100
        y = (i // 5) * 100
        color = "#dc2626" if i in mines else "#16a34a"
        d.rectangle([x+6, y+6, x+94, y+94], fill=color)

    path = "/tmp/result.png"
    img.save(path)
    return path


# ===== RECEIVE ACTIVE BET (PENDING) =====
@app.route("/pending", methods=["POST"])
def pending():
    data = request.json
    bet_id = f"{data['username']}_{data['nonce']}"

    ACTIVE_BETS[bet_id] = data

    text = f"""
🎮 Stake Mines – Provably Fair

👤 Stake Username: {data['username']}
💰 Bet Amount: {data['betAmount']} {data['currency']}
💣 Mines Selected: {data['mines']}

🎲 Client Seed: {data['clientSeed']}
🔒 Server Seed Hash: {data['serverSeedHash']}
🔢 Nonce: {data['nonce']}

⏳ Provably Fair: PENDING
(Server seed not revealed yet)
"""

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text}
    )

    return jsonify(ok=True)


# ===== RECEIVE SERVER SEED (REVEAL) =====
@app.route("/reveal", methods=["POST"])
def reveal():
    data = request.json
    bet_id = f"{data['username']}_{data['nonce']}"

    bet = ACTIVE_BETS.get(bet_id)
    if not bet:
        return jsonify(error="Bet not found"), 400

    server_seed = data["serverSeed"]

    server_hash, mine_tiles, safe_tiles = compute_mines(
        server_seed,
        bet["clientSeed"],
        bet["nonce"],
        bet["mines"]
    )

    # VERIFY HASH
    if server_hash != bet["serverSeedHash"]:
        return jsonify(error="Hash mismatch"), 400

    img_path = generate_image(mine_tiles)

    with open(img_path, "rb") as f:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            files={"photo": f},
            data={
                "chat_id": CHAT_ID,
                "caption": "✅ PROVABLY FAIR VERIFIED\n🟢 Green = Safe\n🔴 Red = Mine"
            }
        )

    return jsonify(verified=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)