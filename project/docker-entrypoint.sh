#!/usr/bin/env bash
./manage.py configure_market
uwsgi --ini uwsgi.ini
