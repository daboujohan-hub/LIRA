FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/srv/lira DATA_DIR=/data
WORKDIR /srv/lira
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x start.sh
CMD ["./start.sh"]
