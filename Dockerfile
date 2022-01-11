FROM python:3.9-slim
WORKDIR ./app

RUN apt update
RUN apt install -y gettext # need for l10n/i18n
RUN apt install -y gcc python3-dev musl-dev # psycopg2 dependencies

# install project requirements
COPY ./requirements.txt .
RUN python3.9 -m pip install -r ./requirements.txt

RUN apt remove gcc -y

COPY ./project .

EXPOSE 8000
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["bash", "./docker-entrypoint.sh"]
