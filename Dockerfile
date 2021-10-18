FROM python:3.10.0-buster

WORKDIR /auto-news

COPY ./auto-news/src .
COPY requirements.txt .

RUN pip install -r requirements.txt

WORKDIR ./output

CMD ["python", "-u", "../auto_news.py"]