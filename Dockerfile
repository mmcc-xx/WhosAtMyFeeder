FROM python:3.8
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
COPY model.tflite .
COPY birdnames.db .
COPY speciesid.py .
COPY webui.py .
COPY templates/ ./templates/
COPY static/ ./static/
COPY requirements.txt .
RUN pip install -r requirements.txt
CMD python ./speciesid.py
