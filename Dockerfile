# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster

WORKDIR /app

RUN apt-get update
RUN pip3 install entsoe-py python-dateutil paho-mqtt requests w1thermsensor

COPY main.py .
COPY utils ./utils

CMD [ "python3", "./main.py"]

