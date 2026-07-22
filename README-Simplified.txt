Steps to transfer:
Copy the entire folder to new computer
Install Python (if not installed)
Run pip install -r requirements.txt
Run python manage.py migrate
Run python setup.py

For fresh database:
Delete db.sqlite3
Run python manage.py migrate
Run python setup.py

For existing data (keep everything):
Just copy db.sqlite3 along with the folder
No need to run migrate again

Default login: admin / admin123
