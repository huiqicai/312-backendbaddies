FROM python:3.8

WORKDIR /root

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD python3 -u app.py