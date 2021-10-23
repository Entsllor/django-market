# Django Marketplace

* Django 3.2 and Python 3.9
* Bootstrap 5 as a CSS framework

## Prerequisites

[Optional] Install virtual environment:

```
python -m virtualenv env
```

[Optional] Activate virtual environment:

On macOS and Linux:

```
source env/bin/activate
```

On Windows:

```
.\env\Scripts\activate
```

## Installation

1. Clone

```
git clone https://github.com/Entsllor/django-market.git
```

2. Set secret key to your environmental variables

On macOS and Linux:

```
export SECRET_KEY=YOUR_SECRET_KEY
```

On Windows:

```
SET SECRET_KEY=YOUR_SECRET_KEY
```

3. Install configure and run server

```
pip install -r requirements.txt
cd project
python manage.py configure_market
python manage.py runserver 0.0.0.0:8000
```

### Test filling

You can use a special command to fill db with test data 
```
python manage.py test_filling
```

If you want to configure filling use this: 

```
python manage.py test_filling custom
```


## Warning

Keep the secret key used in production secret!

Don't run with debug turned on in production!

### How to open admin-panel

1. Create a superuser

```
python manage.py createsuperuser
```

2. Go to http://localhost:8000/admin
3. Enter admin (superuser) username and password

### Currencies
This project supports multi-currencies system.

1. Set constants in /project/project/settings.py
- LANGUAGES (codes of supported languages)
- DEFAULT_CURRENCY (use as default for your data base)
- EXTRA_CURRENCIES (codes of supported currencies)
- CURRENCIES_SYMBOLS (set associated currencies symbols. For example, 'USD': $)
- LOCAL_CURRENCIES (associated currencies with languages. For example, 'en-us': 'USD')

2. Run commands

```
python manage.py create_currencies
python manage.py update_currencies
```

[Optional] Use 'update_currencies' command when you need to update exchanging rates

[Optional] Change rates-source-url if it is necessary
