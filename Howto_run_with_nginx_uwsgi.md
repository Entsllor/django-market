## How to upload this project to your server

### Complete installation from the README.md file

This command must work

```shell
python3 manage.py runserver
```

### Activate virtual environment

```shell
source venv/bin/activate
```

Your environment must have libraries from requirements.txt

```shell
pip3 freeze
cat requirements.txt
```

It is possible to run server without virtual environment, but you should have it

### Install uwsgi

[uWSGI quickstart](https://uwsgi-docs.readthedocs.io/en/latest/WSGIquickstart.html)

You should have python-dev library

```shell
sudo apt install python3.9-dev
```

Install this library to your venv

```shell
pip install uwsgi
```

### Collect static

```shell
cd project
python3 manage.py collectstatic
cd ..
```

[OPTIONAL] You can change media and static files folders in ./project/settings/base_settings.py

```text
# base_settings.py
# ...
STATIC_ROOT = <static-files-path>
MEDIA_ROOT = <media-files-path>
```

### Install Nginx

[Official Nginx documentation](https://www.nginx.com/resources/wiki/start/topics/tutorials/install/)

Ubuntu:

```shell
apt install nginx
sudo systemctl start nginx.service
```

If you've changed some nginx configs you should run:

```shell
sudo systemctl restart nginx.service
```

### Configure Nginx

Write actual paths in nginx.conf and check paths are valid.

You can configure this file as you need. Then create a symbol link.

```shell
sudo usermod -aG www-data $USER
sudo ln -s nginx.conf /etc/nginx/sites-enabled/django-market.conf
sudo systemctl restart nginx.service
# if you want nginx listen 80 port you may delete or edit /etc/nginx/sites-enabled/default
sudo rm /etc/nginx/sites-enabled/default
```


### Run uWSGI

```shell
cd project
uwsgi --ini uwsgi.ini
```
