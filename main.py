import os
import httplib2
import json
import datetime
from functools import wraps
from flask import Flask, session, redirect, render_template, request, url_for
from flask import flash, jsonify, make_response
from flask_seasurf import SeaSurf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_setup import Base, User, Category, Item
from oauth2client import client
from apiclient import discovery


app = Flask(__name__)
csrf = SeaSurf(app)
app.config['TRAP_HTTP_EXCEPTIONS'] = True

# Connect to database
engine = create_engine('sqlite:///catalog.db')
Base.metadata.bind = engine

# Create database session
DBSession = sessionmaker(bind=engine)
db_session = DBSession()

# Custom error handlers


@app.errorhandler(404)
def pageNotFound(Exception):
    return render_template('error404.html'), 404


@app.errorhandler(500)
def pageNotFound(Exception):
    return render_template('error500.html'), 500

# Login/authorize routes and functions


@app.route('/glogin')
def googleLogin():
    """Handles Google login."""

    if 'credentials' not in session:
        return redirect(url_for('goauth2redirect'))

    credentials = client.OAuth2Credentials.from_json(session['credentials'])
    if credentials.access_token_expired:
        return redirect(url_for('goauth2redirect'))
    else:
        http_auth = credentials.authorize(httplib2.Http())
        service = discovery.build('oauth2', 'v2', http=http_auth)
        request = service.userinfo().v2().me().get()
        response = request.execute()
        # print(response)
        # All this data comes in the profile scope
        session['provider'] = 'google'
        session['username'] = response['name']
        session['google_id'] = response['id']
        session['picture'] = response['picture']
        session['email'] = response['email']

        # Check if user exist
        user_id = getUserID(session['email'])
        if not user_id:
            user_id = createUser(session)
        session['user_id'] = user_id

    return redirect(url_for('index'))


@app.route('/goauth2redirect')
def goauth2redirect():
    """Handles Google authentication"""

    # Build a flow object
    flow = client.flow_from_clientsecrets(
          'client_secrets.json',
          scope=['https://www.googleapis.com/auth/userinfo.profile',
                 'https://www.googleapis.com/auth/userinfo.email'],
          redirect_uri=url_for('goauth2redirect', _external=True))
    if 'code' not in request.args:
        # Get authorization code
        auth_uri = flow.step1_get_authorize_url()
        return redirect(auth_uri)
    else:
        # Upgrade authorization code for credentials
        auth_code = request.args.get('code')
        credentials = flow.step2_exchange(auth_code)
        session['credentials'] = credentials.to_json()
        return redirect(url_for('googleLogin'))


# User helper functions

def createUser(session):
    """Creates new user."""
    newUser = User(
                name=session['username'],
                email=session['email'],
                picture=session['picture'])
    db_session.add(newUser)
    db_session.flush()
    db_session.commit()
    return newUser.id


def getUserID(email):
    """Retrieves a user record"""
    try:
        user = db_session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# Logout routes

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/disconnect')
def disconnect():
    if session['provider'] == 'google':
        glogout()
    return redirect(url_for('logout'))


def glogout():
    credentials = client.OAuth2Credentials.from_json(session['credentials'])
    credentials.revoke(httplib2.Http())

# Primary routes

# decorator to allow only authenticated action
def login_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to manage items.')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return decorated_function


@app.route('/')
@app.route('/catalog')
def index():
    """Default page route"""
    categories = db_session.query(Category).all()
    latest = db_session.query(Item).order_by(
        Item.created_at.desc()).limit(10).all()
    return render_template('default.html',
                           categories=categories, latest=latest)


@app.route('/catalog/<int:category_id>')
def displayCategory(category_id):
    """Category page route"""
    categories = db_session.query(Category).all()
    item = db_session.query(Item).filter_by(id=category_id).one()
    category = db_session.query(Category).filter_by(
        id=item.category_id).one()

    # Avoid second database query by running loop in already retrieved data
    for c in categories:
        if c.id == category_id:
            category = c
            break
    items = db_session.query(Item).filter_by(category_id=category.id).all()
    return render_template(
        'category.html', category=category, categories=categories, items=items)


@app.route('/catalog/<int:category_id>/<item_id>')
def displayItem(category_id, item_id):
    """Display item route"""
    category = db_session.query(Category).filter_by(
        id=category_id).one()
    item = db_session.query(Item).filter_by(id=item_id).one()
    return render_template(
        'displayItem.html', item=item, category=category)


@app.route('/catalog/<int:category_id>/new', methods=['POST', 'GET'])
@login_required
def createNew(category_id):
    """New item route."""

    # Create the new item
    if request.method == 'POST':
        newItem = Item(
            category_id=int(request.form['category']),
            name=request.form['name'],
            description=request.form['description'],
            created_at=datetime.datetime.now(),
            user_id=session['user_id'])

        db_session.add(newItem)
        db_session.flush()
        db_session.commit()
        flash('Item successfully created.')
        return redirect(
            url_for('displayItem', category_id=category_id,
                    item_id=newItem.id))
    else:
        categories = db_session.query(Category).all()
        return render_template('createNew.html', categories=categories)


@app.route('/catalog/<int:item_id>/edit', methods=['POST', 'GET'])
@login_required
def edit(item_id):
    """Edit item route"""

    item = db_session.query(Item).filter_by(id=item_id).one()
    category = db_session.query(Category).filter_by(
        id=item.category_id).one()
    categories = db_session.query(Category).all()
    for c in categories:
        if c.id == item.category_id:
            category = c
            break

    # Other users are not allowed to edit items except the owner
    if item.user_id != session['user_id']:
        return redirect(
            url_for('displayItem', category_id=category.id,
                    item_id=item.id))

    if request.method == 'POST':
        if request.form['category']:
            item.category_id = request.form['category']
        if request.form['name']:
            item.name = request.form['name']
        if request.form['description']:
            item.description = request.form['description']

        db_session.add(item)
        db_session.commit()
        flash('Item succesfully updated.')
        return redirect(
            url_for('displayItem', category_id=category.id, item_id=item.id))
    else:
        return render_template('edit.html', category=category,
                               categories=categories, item=item)


@app.route('/catalog/<int:item_id>/delete', methods=['POST', 'GET'])
@login_required
def delete(item_id):
    """Item delete route"""

    item = db_session.query(Item).filter_by(id=item_id).one()
    category = db_session.query(Category).filter_by(
        id=item.category_id).one()

    # Other users are not allowed to delete items except the owner
    if item.user_id != session['user_id']:
        return redirect(
            url_for('displayItem', category_id=category.id,
                    item_id=item.id))

    if request.method == 'POST':
        db_session.delete(item)
        db_session.commit()
        flash('Item successfully deleted.')
        return redirect(
            url_for('displayCategory', category_id=category.id))
    else:
        return render_template(
            'delete.html', category=category, item=item)


# API Endpoint for JSON


@app.route('/api')
@app.route('/catalog/api')
def indexJSON():
    categories = db_session.query(Category).all()
    catalog = []
    for c in categories:
        catalog.append(c.serialize)
        items = db_session.query(Item).filter_by(category_id=c.id).all()
        catalog[-1]['Items'] = [i.serialize for i in items]
    return jsonify(Categories=catalog)

# Get all items in a single category with a given category id
@app.route('/api/<int:category_id>')
def categoryAPI(category_id):
    items = db_session.query(Item).filter_by(category_id=category_id).all()
    items_list = []
    for i in items:
        items_list.append(i.serialize)
    print(items_list)
    return jsonify(Items=items_list)

# Get a single item with a given category and item ID
@app.route('/api/<int:category_id>/<int:item_id>')
def itemAPI(category_id, item_id):
    items = db_session.query(Item).filter_by(id=item_id).one()
    return jsonify(Item=items.serialize)

if __name__ == "__main__":
    app.secret_key = 'super secret key'
    app.debug = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
