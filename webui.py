from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import base64
from datetime import datetime
import yaml
from EcoNameTranslator import to_common

app = Flask(__name__)
config = None


def get_common_names(scientific_name):
    conn = sqlite3.connect('speciesid.db')
    cursor = conn.cursor()

    # Look up the scientific name in the birdnames table
    cursor.execute("SELECT common_names FROM birdnames WHERE scientific_name = ?;", (scientific_name,))
    row = cursor.fetchone()

    if row:
        # If the scientific name is found, return the common names from the table
        common_names_str = row[0]
        common_names = common_names_str.split(',')
    else:
        # If the scientific name is not found, use the to_common() function to get the common names
        common_names = to_common([scientific_name])[scientific_name][1]

        # Store the common names in the birdnames table for faster access later
        common_names_str = ','.join(common_names)
        cursor.execute("INSERT INTO birdnames (scientific_name, common_names) VALUES (?, ?);",
                       (scientific_name, common_names_str))
        conn.commit()

    conn.close()
    return common_names


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

    commonnames = []
    for row in rows:
        scientificname = row[4]
        commonname = get_common_names(scientificname)
        commonnames.append(commonname)

    return rows, commonnames


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
    commonnames = []
    for row in rows:
        cursor.execute("""  
            SELECT image  
            FROM detections  
            WHERE category_name = ? AND score = ? AND date(detection_time) = ?  
        """, (row[0], row[3], date))

        image_data = cursor.fetchone()[0]
        images.append(base64.b64encode(image_data).decode("utf-8"))
        scientificname = row[1]
        commonname = get_common_names(scientificname)

        # This should be the list of common names associated with the sciency name
        commonnames.append(commonname)
    conn.close()
    return rows, images, commonnames


@app.route('/mostrecent')
def recent_records():
    records, commonnames = get_most_recent_detections()
    for i, record in enumerate(records):
        # Encode the image as base64 for embedding in the HTML
        records[i] = list(record)
        records[i][6] = base64.b64encode(record[6]).decode("utf-8")
    zipped_data = zip(records, commonnames)
    return render_template('most_recent.html', zipped_data=zipped_data)


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
    data, images, commonnames = frequencies_by_date(date, sort_order)
    zipped_data = zip(data, images, commonnames)
    return render_template('results.html', zipped_data=zipped_data, date=date)


def load_config():
    global config
    file_path = './config/config.yml'
    with open(file_path, 'r') as config_file:
        config = yaml.safe_load(config_file)


def setupdb():
    conn = sqlite3.connect("speciesid.db")
    cursor = conn.cursor()
    cursor.execute("""  
        CREATE TABLE IF NOT EXISTS birdnames (  
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            scientific_name TEXT NOT NULL,  
            common_names TEXT NOT NULL 
        )  
    """)
    conn.commit()


if __name__ == '__main__':
    load_config()
    setupdb()
    app.run(debug=True, host=config['webui']['host'], port=config['webui']['port'])
