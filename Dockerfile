FROM python:3.9-slim
COPY ./project ./app
COPY ./requirements.txt .
RUN apt update
RUN apt install gettext -y
RUN python3.9 -m pip install -r ./requirements.txt
WORKDIR ./app

RUN python3.9 manage.py configure_market

EXPOSE 5050
ENV DJANGO_SECRET_KEY=SECRET_KEY
ENV DJANGO_SETTINGS_MODULE=project.settings.production

ENTRYPOINT ["python3", "manage.py", "runserver", "0.0.0.0:5050"]

