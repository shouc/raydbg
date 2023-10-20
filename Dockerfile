FROM ubuntu:20.04

# install python3 and pip3
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --upgrade pip
RUN pip3 install ray
RUN mkdir /app

COPY README.md /app
COPY setup.py /app
COPY examples /app/examples
COPY raydbg /app/raydbg

WORKDIR /app
RUN pip3 install -e .
RUN raydbg init