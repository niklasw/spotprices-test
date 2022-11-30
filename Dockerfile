# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster

WORKDIR /app

RUN pip3 install entsoe-py python-dateutil paho-mqtt

COPY main.py .
COPY utils ./utils

CMD [ "python3", "./main.py"]

