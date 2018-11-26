import sys
import os
import inspect
import json
# Insert our lib directory into the module search path
current_file = inspect.getfile(inspect.currentframe())
base_path = os.path.dirname(os.path.abspath(current_file))
sys.path.insert(0, os.path.join(base_path, 'lib'))
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
import boto3


if (sys.version_info.major == 2 and sys.version_info.minor < 9):
  print("Python version is < 2.7.9. You will get warnings about SNI (Server Name Indication) when usig HTTPS connections")


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

def connect_ecs():
  # Reset our connection and bucket variables
  app.config.update(
    CLIENT = None,
    BUCKET_LIST = None,
    BUCKET = None,
  )
  app.config['CLIENT'] = boto3.client(
    's3',
    aws_access_key_id=app.config['ACCESS_ID'],
    aws_secret_access_key=app.config['ACCESS_KEY'],
    aws_session_token=app.config['TOKEN'],
    endpoint_url=app.config['ENDPOINT'],
  )
  if app.config['CLIENT']:
    try:
      app.config['BUCKET_LIST'] = app.config['CLIENT'].list_buckets()
    except Exception as e:
      app.config['CLIENT'] = None
  
@app.route("/", methods=['GET'])
def home():
  errors = None
  return render_template('home.html', errors=errors)
  
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
  print("Status of client: %s"%app.config['CLIENT'])
  
  if request.method == 'POST':
    print("Request args: %s"%request.args)
    print("Form: %s"%request.form)
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
      buckets = sorted(app.config['BUCKET_LIST'].get('Buckets', None), key=lambda x: x.get('Name'))
      bucket_form.bucket.choices = [(x.get('Name'), x.get('Name')) for x in buckets]
      if bucket_form.validate_on_submit():
        app.config['BUCKET'] = request.form.get('bucket')
        return redirect("/config")
      flash('Unknown error encountered using selected bucket: %s'%request.form.get('bucket'), 'error')
    else:
      print("Got error")
  elif request.method == 'GET':
    if app.config['CLIENT']:
      buckets = sorted(app.config['BUCKET_LIST'].get('Buckets', None), key=lambda x: x.get('Name'))
      bucket_form.bucket.choices = [(x.get('Name'), x.get('Name')) for x in buckets]
      print("Bucket value: %s"%app.config['BUCKET'])
    
  return render_template('configuration.html', errors=errors, connect_form=connect_form, bucket_form=bucket_form)
  
if __name__ == "__main__":
  app.run(debug=True)