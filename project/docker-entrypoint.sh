#!/usr/bin/env bash

# Wait for db
if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]
then
  echo "Wait for Database - ${DB_HOST}:${DB_PORT}"
  timeout 20 bash -c 'until printf "" 2>>/dev/null >>/dev/tcp/$0/$1; do sleep 0.1; done' "${DB_HOST}" "${DB_PORT}"
  echo "Database - ${DB_HOST}:${DB_PORT} is loaded"
fi

./manage.py configure_market
uwsgi --ini uwsgi.ini
