import sys
import os
import inspect
import json
import logging
import logging.config

# Insert our lib directory into the module search path
current_file = inspect.getfile(inspect.currentframe())
base_path = os.path.dirname(os.path.abspath(current_file))
sys.path.insert(0, os.path.join(base_path, 'lib'))
import xmltodict
import requests
from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import flash
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms import PasswordField
from wtforms import BooleanField
from wtforms import SubmitField
from wtforms import SelectField
from wtforms import HiddenField
from wtforms.fields.html5 import URLField
from wtforms.widgets.core import PasswordInput
from wtforms.validators import DataRequired
# Monkey patch awsauth to add headers used by ECS (relies on 'requests' module)
from awsauth.awsauth import S3Auth
for param in ['searchmetadata', 'query']:
  if param not in S3Auth.special_params:
    S3Auth.special_params.append(param)


if (sys.version_info.major == 2 and sys.version_info.minor < 9):
  print("Python version is < 2.7.9. You will get warnings about SNI (Server Name Indication) when usig HTTPS connections")


# Global variables
# Setup logging here before the Flask app is instantiated
logging.config.dictConfig({
  'version': 1,
  'formatters': {'default': {
    'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
  }},
  'handlers': {'wsgi': {
    'class': 'logging.StreamHandler',
    'stream': 'ext://flask.logging.wsgi_errors_stream',
    'formatter': 'default'
  }},
  'root': {
    'level': 'DEBUG',
    'handlers': ['wsgi']
  }
})


app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config.Config')
app.config.from_pyfile('application.cfg', silent=True)
app.config.from_envvar('EMC_META_SEARCH_CONFIG', silent=True)


class VisiblePasswordField(PasswordField):
  widget = PasswordInput(hide_value= False)

class ConnectForm(FlaskForm):
  ecs_username = StringField('ECS Username', validators=[DataRequired()], default=lambda: app.config['ACCESS_ID'])
  if app.config['VISIBLE_PASSWORD']:
    ecs_password = VisiblePasswordField('ECS Password', validators=[DataRequired()], default=lambda: app.config['ACCESS_KEY'])
  else:
    ecs_password = PasswordField('ECS Password', validators=[DataRequired()])
  ecs_endpoint = URLField('ECS Endpoint', validators=[DataRequired()], default=lambda: app.config['ENDPOINT'])
  ecs_replication_group = StringField('ECS Replication Group', validators=[DataRequired()], default=lambda: app.config['TOKEN'])
  type = HiddenField('type', default='connect')
  submit = SubmitField('Connect')

class BucketForm(FlaskForm):
  bucket = SelectField('Bucket', validators=[DataRequired()], default=lambda: app.config['BUCKET'])
  type = HiddenField('type', default='bucket')
  submit = SubmitField('Select bucket')

def connect_ecs(bucket=None):
  # Reset our connection and bucket variables
  app.config.update(
    CLIENT = None,
    BUCKET_LIST = {},
    BUCKET_MAP = {},
    BUCKET = bucket,
  )
  if not (app.config['ACCESS_ID'] and app.config['ACCESS_KEY']
          and app.config['TOKEN'] and app.config['ENDPOINT']):
    # Do not attempt a connect unless all 4 values are available
    app.logger.info('Cannot connect to ECS. Not all variables defined')
    return
  app.logger.info('Trying to connect to ECS instance at: %s'%app.config['ENDPOINT'])
  client = requests.Session()
  if client:
    try:
      app.config['CLIENT'] = client
      client.auth = S3Auth(
          app.config['ACCESS_ID'],
          app.config['ACCESS_KEY'],
          service_url=app.config['ENDPOINT']
      )
      resp = client.get(app.config['ENDPOINT'])
      # TODO: Need to add error handling!
      if resp.content:
        resp_dict = xmltodict.parse(resp.content)
        app.config['BUCKET_LIST'] = resp_dict['ListAllMyBucketsResult']['Buckets']['Bucket']
        for bucket in app.config['BUCKET_LIST']:
          app.config['BUCKET_MAP'][bucket['Name']] = bucket
        if app.config['BUCKET'] and app.config['BUCKET'] not in app.config['BUCKET_MAP'].keys():
          app.config['BUCKET'] = None
          flash('Invalid bucket name for ECS endpoint: %s'%app.config['ENDPOINT'], 'error')
    except Exception as e:
      app.logger.exception(e)
      app.config['CLIENT'] = None
  
@app.route("/", methods=['GET'])
def home():
  errors = None
  app.logger.info('Status of client: %s'%app.config['CLIENT'])
  data = {}
  client = app.config['CLIENT']
  if client:
    resp = client.get(app.config['ENDPOINT'])
    resp_dict = xmltodict.parse(resp.content)
    data['all_buckets'] = json.dumps(resp_dict, indent=4, sort_keys=True)
    
    resp = client.get(app.config['ENDPOINT'] + '/' + app.config['BUCKET'], params='searchmetadata')
    resp_dict = xmltodict.parse(resp.content)
    data['search'] = json.dumps(resp_dict, indent=4, sort_keys=True)
      
  return render_template('home.html', errors=errors, raw=data)
  
@app.route("/search", methods=['GET', 'POST'])
def search():
  errors = None
  return render_template('search.html', errors=errors)
  
@app.route("/config", methods=['GET', 'POST'])
def configuration():
  errors = None
  buckets = []
  connect_form = ConnectForm()
  bucket_form = BucketForm()
  app.logger.info('Status of client: %s'%app.config['CLIENT'])
  app.logger.debug('Request args: %s'%request.args)

  if request.method == 'POST':
    if request.form.get('type') == 'connect':
      if connect_form.validate_on_submit():
        app.config.update(
          ACCESS_ID = request.form.get('ecs_username'),
          ACCESS_KEY = request.form.get('ecs_password'),
          TOKEN = request.form.get('ecs_replication_group'),
          ENDPOINT = request.form.get('ecs_endpoint'),
        )
        connect_ecs()
        # Check if client is valid or the connect succeeded. If it did not, render an error
        if app.config['CLIENT']:
          return redirect("/config")
        errors = ['Could not connect using provided ECS credentials. Please check the values and try again.']
        flash('Could not connect using provided ECS credentials. Please check the values and try again.', 'error')
    elif request.form.get('type') == 'bucket':
      bucket_form.bucket.choices = [(x, x) for x in sorted(app.config['BUCKET_MAP'].keys())]
      if bucket_form.validate_on_submit():
        app.config['BUCKET'] = request.form.get('bucket')
        return redirect("/config")
      flash('Unknown error encountered using selected bucket: %s'%request.form.get('bucket'), 'error')
    else:
      app.logger.critical('Unknown form type received: %s'%request.form.get('type'))
      flash('Unknown form type received: %s'%request.form.get('type'), 'error')
  elif request.method == 'GET':
    if app.config['CLIENT']:
      bucket_form.bucket.choices = [(x, x) for x in sorted(app.config['BUCKET_MAP'].keys())]
      app.logger.debug('Bucket selected: %s'%app.config['BUCKET'])
    
  return render_template('configuration.html', errors=errors, connect_form=connect_form, bucket_form=bucket_form)
  
if __name__ == "__main__":
  connect_ecs(app.config['BUCKET'])
  app.run(debug=True)
