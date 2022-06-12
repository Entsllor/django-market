# Django Marketplace

* Django 4 and Python 3.9
* Bootstrap 5 as a CSS framework

## Prerequisites

Install virtual environment:

```shell
python3 -m venv venv
# or
# pip3 install virtualenv 
# python3 -m virtualenv venv
```

Activate virtual environment:

On macOS and Linux:

```shell
source venv/bin/activate
```

On Windows:

```
.\venv\Scripts\activate
```

## Installation

```shell
git clone https://github.com/Entsllor/django-market
```

## Configuration

Create .env file in django-market/project
and put project env variables you need according to a .env.template

```shell
cd django-market/project
# [optional] use template
cat .env.template > .env
# edit file
vim .env
```

[WARNING] Keep the secret key used in production secret!

[WARNING] Don't run with debug turned on in production!

Install requirements

```shell
pip3 install -r requirements.txt
```

Final configuration

```shell
python3 manage.py configure_market
```

## Running

```shell
python3 manage.py runserver
```

### Test filling

You can use a special command to fill db with test data 
```shell
python3 manage.py test_filling
```

If you want to configure filling use this: 

```shell
python3 manage.py test_filling --custom
```

### How to open admin-panel

1. Create a superuser

```shell
python3 manage.py createsuperuser
```

2. Go to http://localhost:8000/admin
3. Enter admin (superuser) username and password

### Currencies
This project supports multi-currencies system.

1. Set constants in /project/project/settings/base_settings.py
- LANGUAGES (codes of supported languages)
- DEFAULT_CURRENCY (use as default for your database)
- EXTRA_CURRENCIES (codes of supported currencies)
- CURRENCIES_SYMBOLS (set associated currencies symbols. For example, 'USD': $)
- LOCAL_CURRENCIES (associated currencies with languages. For example, 'en-us': 'USD')

2. Run commands

```shell
python3 manage.py create_currencies
# [optional] Use 'update_currencies' command when you need to update exchanging rates
python3 manage.py update_currencies
```
