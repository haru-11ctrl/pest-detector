from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO
import sqlite3

app = Flask(__name__)
socketio = SocketIO(app)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS insects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insect TEXT,
    count INTEGER,
    confidence REAL,
    image_url TEXT,
    timestamp TEXT
)
""")
conn.commit()


# ---------------- API ----------------
@app.route('/data/ingest', methods=['POST'])
def ingest():
    data = request.json
    print("Received:", data)

    cursor.execute("""
    INSERT INTO insects (insect, count, confidence, image_url, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """, (
        data.get('insect_species'),
        data.get('count'),
        data.get('confidence'),
        data.get('image_url'),
        data.get('timestamp')
    ))
    conn.commit()

    # Emit live update
    socketio.emit('new_data', data)

    return jsonify({"status": "success"})


# ---------------- DASHBOARD ----------------
@app.route('/')
def dashboard():

    cursor.execute("SELECT * FROM insects ORDER BY id DESC")
    rows = cursor.fetchall()

    records = []
    for r in rows:
        records.append({
            "insect_species": r[1],
            "count": r[2],
            "confidence": r[3],
            "image_url": r[4],
            "timestamp": r[5]
        })

    html = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Insect Monitor</title>

<style>
body {
    margin: 0;
    font-family: -apple-system, sans-serif;
    background: #0f172a;
    color: #fff;
}

.header {
    position: sticky;
    top: 0;
    background: #020617;
    padding: 15px;
    text-align: center;
    font-size: 20px;
    font-weight: bold;
}

.container {
    padding: 10px;
}

.card {
    background: #1e293b;
    border-radius: 15px;
    margin-bottom: 15px;
    padding: 12px;
}

.card img {
    width: 100%;
    border-radius: 10px;
}

.row {
    display: flex;
    justify-content: space-between;
    margin-top: 8px;
}

.badge {
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
}

.high { background: #16a34a; }
.medium { background: #f59e0b; }
.low { background: #dc2626; }

.chart {
    background: #1e293b;
    padding: 10px;
    border-radius: 15px;
    margin-bottom: 15px;
}
</style>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>

</head>

<body>

<div class="header">🐛 Insect Monitor</div>

<div class="container">

<!-- Filter -->
<select id="filter" onchange="filterData()">
<option value="all">All</option>
{% for item in records %}
<option value="{{item.insect_species}}">{{item.insect_species}}</option>
{% endfor %}
</select>

<!-- Chart -->
<div class="chart">
<canvas id="chart"></canvas>
</div>

{% for item in records %}
<div class="card" data-type="{{item.insect_species}}">

<img src="{{item.image_url}}">

<div class="row">
    <div><b>{{item.insect_species}}</b></div>
    <div>{{"%.2f"|format(item.confidence)}}</div>
</div>

<div class="row">
    <div>Count: {{item.count}}</div>
    <div>{{item.timestamp}}</div>
</div>

{% if item.confidence > 0.8 %}
<span class="badge high">High</span>
{% elif item.confidence > 0.5 %}
<span class="badge medium">Medium</span>
{% else %}
<span class="badge low">Low</span>
{% endif %}

</div>
{% endfor %}

</div>

<script>

// -------- FILTER --------
function filterData() {
    let selected = document.getElementById("filter").value;
    let cards = document.getElementsByClassName("card");

    for (let card of cards) {
        let type = card.getAttribute("data-type");
        card.style.display = (selected === "all" || type === selected) ? "block" : "none";
    }
}

// -------- CHART --------
const data = {{ records|tojson }};
const counts = {};

data.forEach(item => {
    counts[item.insect_species] = (counts[item.insect_species] || 0) + 1;
});

new Chart(document.getElementById('chart'), {
    type: 'doughnut',
    data: {
        labels: Object.keys(counts),
        datasets: [{
            data: Object.values(counts)
        }]
    }
});

// -------- LIVE UPDATE --------
var socket = io();

socket.on('new_data', function(data) {
    location.reload();
});

</script>

</body>
</html>
"""
    return render_template_string(html, records=records)


# ---------------- RUN ----------------
if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000)