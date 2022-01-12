FROM python:3.9-slim

RUN apt update
RUN apt install -y gettext # need for l10n/i18n
RUN apt install -y gcc python3-dev musl-dev # psycopg2 dependencies

WORKDIR /usr/src/dj-market

# install project requirements
COPY ./requirements.txt .
RUN python3.9 -m pip install -r ./requirements.txt

RUN apt remove gcc -y

COPY . .

EXPOSE 8000
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["bash", "./docker-entrypoint.sh"]
