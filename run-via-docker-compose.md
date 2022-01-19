# Run this project via docker-compose

## Copy docker-compose file

```shell
cp docker-compose.yml /path/you/need/dj-market/docker-compose.yml
# or if you use ssh
scp docker-compose.yml username@remote_address:/path/you/need/dj-market/docker-compose.yml
```

## Configure project

Create a project directory and .env file
```shell
#vim /path/to/copied-docker-compose-file/project/.env
mkdir "project"
vim ./project/.env
```

You should set env variable as in project/.env.template.
First set DJANGO_SETTINGS_MODULE and DJANGO_SECRET_KEY, then 
set variables related with your database.

If you use Postgres as database you should set DB_HOST=db.

If you get error 400 (Bad Request) when you up docker-compose 
check if DJANGO_ALLOWED_HOSTS is configured in .env file.

## Configure nginx

```shell
mkdir "nginx/conf.d"
# [optional] use template
cp "nginx/conf.d/nginx.conf.template" "nginx/conf.d/dj-market.conf"
# write your nginx config
vim "nginx/conf.d/dj-market.conf"
```

[optional] You may put your ssl files in ./nginx/ssl/
```shell
# ssl_certificate
mv /path-to-ssl_certificate/examle.org.crt ./nginx/ssl
# ssl_certificate_key
mv /path-to-ssl_certificate_key/examle.org.key ./nginx/ssl
# ssl_trusted_certificate
mv /path-to-ssl_trusted_certificate/ca.crt ./nginx/ssl
```


## Install docker and docker-compose

[Install Docker](https://docs.docker.com/engine/install/ubuntu/)

[Install Docker-compose](https://docs.docker.com/compose/install/)

## Pull

```shell
docker-compose pull
```

## Run

```shell
docker-compose up --no-build
```
