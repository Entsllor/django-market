FROM python:3.9-slim
COPY ./project /app/
COPY ./requirements.txt /app/
RUN apt update
RUN apt install gettext -y
RUN python3.9 -m pip install -r /app/requirements.txt
WORKDIR ./app

RUN python3.9 manage.py configure_market

EXPOSE 5050
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=project.settings.production
# SECURITY WARNING: you should to change this secret key and keep it used in production secret
ENV DJANGO_SECRET_KEY=Your_Secret_Key

ENTRYPOINT ["python3", "manage.py", "runserver", "0.0.0.0:5050"]
