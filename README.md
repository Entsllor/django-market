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

3. Install requirements and run server

```
pip install -r requirements.txt
cd project
python manage.py makemigrations
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
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
