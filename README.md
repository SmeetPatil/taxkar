# TaxKar
TaxKar is a an online website (G2C) that can be used to assess income tax, GST on items and Foreign Exchange (Forex)

## Steps to run this app : 
1. First download the code and open it in preferred IDE as a project
2. Create a virtual environment in the project directory itself to run the project using : 
   > py -m venv .venv
3. Start the virtual environment using :
   > .venv\Scripts\activate.bat
4. Install the requirements for the project as stated in the file using :
   > pip install -r requirements.txt
5. Once the requirements are installed, run migrations in the project using :
   > python manage.py makemigrations
   >
   > python manage.py migrate
   >
   > python manage.py collectstatic
6. Create a superuser and remember the username and password. Use :
   > python manage.py createsuperuser
7. Now that everything is ready, run the app using :
   > python manage.py runserver
8. Click on the localhost server link in the terminal and you should be greeted with the home webpage.

## Contributors 
### Smeet Patil
### Soham Patil
### Soham Pawar
