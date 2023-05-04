from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import base64
from datetime import datetime
import yaml

app = Flask(__name__)
config = None

def get_most_recent_detections(limit=50):
    conn = sqlite3.connect("speciesid.db")
    cursor = conn.cursor()

    cursor.execute("""  
        SELECT *  
        FROM detections  
        ORDER BY detection_time DESC  
        LIMIT ?  
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()
    return rows


from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import base64
from datetime import datetime

app = Flask(__name__)


def frequencies_by_date(date, sort_order):
    conn = sqlite3.connect("speciesid.db")
    cursor = conn.cursor()

    query = """  
        SELECT category_name, display_name, COUNT(*) as frequency, MAX(score) as max_score  
        FROM detections  
        WHERE date(detection_time) = ?  
        GROUP BY category_name  
        ORDER BY frequency {}  
    """.format(sort_order)

    cursor.execute(query, (date,))
    rows = cursor.fetchall()

    images = []
    for row in rows:
        cursor.execute("""  
            SELECT image  
            FROM detections  
            WHERE category_name = ? AND score = ? AND date(detection_time) = ?  
        """, (row[0], row[3], date))

        image_data = cursor.fetchone()[0]
        images.append(base64.b64encode(image_data).decode("utf-8"))

    conn.close()
    return rows, images


@app.route('/mostrecent')
def recent_records():
    records = get_most_recent_detections()
    for i, record in enumerate(records):
        # Encode the image as base64 for embedding in the HTML
        records[i] = list(record)
        records[i][6] = base64.b64encode(record[6]).decode("utf-8")
    return render_template('most_recent.html', records=records)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        date = request.form['date']
        sort_order = request.form['sort_order']
        return redirect(url_for('results', date=date, sort_order=sort_order))

    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html', today=today)


@app.route('/results')
def results():
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    sort_order = request.args.get('sort_order', 'DESC')
    data, images = frequencies_by_date(date, sort_order)
    zipped_data = zip(data, images)
    return render_template('results.html', zipped_data=zipped_data, date=date)


def load_config():
    global config
    file_path = './config/config.yml'
    with open(file_path, 'r') as config_file:
        config = yaml.safe_load(config_file)


if __name__ == '__main__':
    load_config()
    app.run(debug=True, host=config['webui']['host'], port=config['webui']['port'])
