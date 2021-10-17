FROM python:3.10.0

WORKDIR ~/auto-news

COPY ./auto-news/src .
COPY requirements.txt .

RUN pip install -r requirements.txt

WORKDIR ~/auto-news/output

CMD ["python", "-u", "../auto_news.py"]