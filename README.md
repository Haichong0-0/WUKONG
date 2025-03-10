# WUKONG
$ source venv/bin/activate  
$ pip install -r requirements.txt    
$ pip install "moto<4.0.0"   
$ python manage.py migrate  
$ python manage.py makemigrations  
$ python3 manage.py seed  
$ python manage.py loaddata tickets/tests/fixtures/default_superuser.json  
$ python manage.py runserver  
$ python manage.py test tickets  
$ coverage run --source=tickets manage.py test tickets  
$ coverage html  
