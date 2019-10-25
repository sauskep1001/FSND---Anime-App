# Anime Catalog

Full Stack Anime Catalog Management App.


## Dependencies :-

* Flask
* SQLAlchemy
* httplib2
* apiclient
* Flask-SeaSurf
* google-api-python-client
* httplib2
* Jinja2

#### Install deps using :

```
$ pip3 install -r requirements.txt
```


### Get Google credentials file for OAuth2 - 

* Go to https://console.cloud.google.com/apis/credentials/oauthclient and setup Google OAuth API Credentials. 

* Enter ```http://localhost:5000``` in the Authorized JavaScript origins and ```http://localhost:5000/goauth2redirect``` in the Authorized redirect URIs.

* After saving, download and rename the file to ```client_secrets.json``` and replace that file in the project directory.


## Run the project :-

* Initialize the database : ```$ python3 db_setup.py```

* Seed the db with some anime categories and anime in each category : ```python3 seed_db.py```

* Launch the application : ```$ python main.py```

* Open the browser and go to http://localhost:5000


## Access API :-

A REST API endpoint is provided which can be consumed by any client without auth and returns JSON of all items, access it here - http://localhost:5000/api

### Improvements - 

* Use a modern frontend framework like React, Vue and consume endpoints from the server instead of boring templating
* GitHub, LinkedIn, FB are widely used so add it's auth.
* UI could be better.