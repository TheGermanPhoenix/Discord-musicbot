FROM python:3

WORKDIR /app

COPY requirements.txt ./
RUN python3 -m pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y ffmpeg

COPY . /app/

CMD [ "python3", "-u",  "start.py" ]
