from flask import Flask, render_template, request, jsonify
import json
import requests
from bs4 import BeautifulSoup
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

app = Flask(__name__)

# ---------------- LOAD DATA ----------------
with open("laptops.json") as f:
    laptops = json.load(f)

# ---------------- FIS SYSTEM ----------------
budget = ctrl.Antecedent(np.arange(0, 101, 1), 'budget')
performance = ctrl.Antecedent(np.arange(0, 101, 1), 'performance')
battery = ctrl.Antecedent(np.arange(0, 101, 1), 'battery')
portability = ctrl.Antecedent(np.arange(0, 101, 1), 'portability')

output = ctrl.Consequent(np.arange(0, 101, 1), 'output')

# Memberships
for var in [budget, performance, battery, portability]:
    var['low'] = fuzz.trimf(var.universe, [0, 0, 40])
    var['medium'] = fuzz.trimf(var.universe, [30, 50, 70])
    var['high'] = fuzz.trimf(var.universe, [60, 100, 100])

output['budget'] = fuzz.trimf(output.universe, [0, 0, 25])
output['student'] = fuzz.trimf(output.universe, [20, 40, 60])
output['ultrabook'] = fuzz.trimf(output.universe, [50, 70, 85])
output['gaming'] = fuzz.trimf(output.universe, [75, 100, 100])

# RULES
rules = [
    ctrl.Rule(performance['high'], output['gaming']),
    ctrl.Rule(budget['high'] & performance['high'], output['gaming']),
    ctrl.Rule(battery['high'] & portability['high'], output['ultrabook']),
    ctrl.Rule(budget['medium'] & performance['medium'], output['student']),
    ctrl.Rule(budget['low'] & performance['low'], output['budget']),
    ctrl.Rule(budget['low'] & battery['high'], output['student']),
    ctrl.Rule(performance['high'] & battery['medium'], output['gaming']),
    ctrl.Rule(performance['medium'] & portability['high'], output['ultrabook']),
    ctrl.Rule(budget['medium'] & battery['high'] & portability['high'], output['ultrabook']),
    ctrl.Rule(budget['high'] & battery['high'], output['ultrabook']),
    ctrl.Rule(budget['medium'] & performance['high'], output['gaming']),
    ctrl.Rule(budget['low'] & performance['medium'], output['student']),
    ctrl.Rule(budget['medium'] & portability['medium'], output['student']),
    ctrl.Rule(budget['high'] & performance['medium'], output['ultrabook'])
]

system = ctrl.ControlSystem(rules)

def compute_score(lap, user):
    sim = ctrl.ControlSystemSimulation(system)
    try:
        sim.input['budget'] = min(lap['price'] / 2000, 100)
        sim.input['performance'] = user['performance']
        sim.input['battery'] = user['battery']
        sim.input['portability'] = user['portability']
        sim.compute()
        return sim.output['output']
    except:
        return 50

# ---------------- SCRAPERS ----------------
def scrape_amazon():
    results = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://www.amazon.in/s?k=laptop", headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select("div.s-result-item")[:5]
        for item in items:
            name = item.select_one("h2 span")
            price = item.select_one(".a-price-whole")
            img = item.select_one("img")
            link = item.select_one("a.a-link-normal")

            if name and price:
                results.append({
                    "name": name.text,
                    "price": int(price.text.replace(',', '')),
                    "image": img['src'] if img else "",
                    "rating": 4,
                    "specs": "Amazon Laptop",
                    "link": "https://amazon.in" + link['href'] if link else "#"
                })
    except:
        pass
    return results

def scrape_flipkart():
    results = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://www.flipkart.com/search?q=laptop", headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select("._1AtVbE")[:5]
        for item in items:
            name = item.select_one("._4rR01T")
            price = item.select_one("._30jeq3")
            img = item.select_one("img")
            link = item.select_one("a")

            if name and price:
                results.append({
                    "name": name.text,
                    "price": int(price.text.replace('₹','').replace(',','')),
                    "image": img['src'] if img else "",
                    "rating": 4,
                    "specs": "Flipkart Laptop",
                    "link": "https://flipkart.com" + link['href'] if link else "#"
                })
    except:
        pass
    return results

# ---------------- ROUTES ----------------
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/main')
def main():
    return render_template('index.html')

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json

    user = {
        "performance": int(data.get("performance", 50)),
        "battery": int(data.get("battery", 50)),
        "portability": int(data.get("portability", 50))
    }

    min_b = int(data.get("budget_min", 0))
    max_b = int(data.get("budget_max", 200000))

    # ✅ NEW FILTER BLOCK (YOUR ADDITION)
    brand = data.get("brand", "")
    processor = data.get("processor", "")
    ram = data.get("ram", "")

    dataset = []

    for l in laptops:
        if not (min_b <= l['price'] <= max_b):
            continue

        if brand and brand.lower() not in l.get('brand', '').lower():
            continue

        if processor and processor.lower() not in l.get('processor', '').lower():
            continue

        if ram and str(ram) not in str(l.get('ram', '')):
            continue

        dataset.append(l)

    scraped = scrape_amazon() + scrape_flipkart()

    combined = dataset + scraped

    for lap in combined:
        lap['score'] = compute_score(lap, user)

    combined.sort(key=lambda x: -x['score'])

    for i, lap in enumerate(combined):
        lap['badge'] = "Best Match" if i == 0 else "Almost Best Match" if i == 1 else ""

    return jsonify(combined[:12])

if __name__ == '__main__':
    app.run(debug=True)