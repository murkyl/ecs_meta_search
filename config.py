import os

class Config(object):
  SECRET_KEY = os.environ.get('SECRET_KEY') or 'ecs_meta_search_secrets'
  ACCESS_ID = None
  ACCESS_KEY = None
  TOKEN = None
  ENDPOINT = None
  BUCKET = None
  CLIENT = None
  VISIBLE_PASSWORD = True
