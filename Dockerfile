# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster

WORKDIR /app

RUN apt-get update
RUN apt-get install -y libblas-dev liblapack-dev binutils binutils-arm-linux-gnueabihf binutils-common blt bzip2 cpp cpp-8 file fontconfig-config fonts-lyx g++ g++-8 gcc gcc-8
RUN pip3 install entsoe-py python-dateutil paho-mqtt

COPY main.py .
COPY utils ./utils

CMD [ "python3", "./main.py"]

