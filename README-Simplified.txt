Steps to transfer:
Copy the entire folder to new computer
Install Python (if not installed)
Run pip install -r requirements.txt
Run python manage.py migrate


For fresh database:
Delete db.sqlite3
Run python manage.py migrate
Run python manage.py createsuperuser to create admin account
For existing data (keep everything):

Just copy db.sqlite3 along with the folder
No need to run migrate again