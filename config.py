import os

class Config(object):
  DEBUG = os.environ.get('ECS_META_SEARCH_DEBUG') or False
  SECRET_KEY = os.environ.get('ECS_META_SEARCH_SECRET_KEY') or 'ecs_meta_search_secrets'
  SESSION_COOKIE_NAME = 'ecs_meta_search'
  ACCESS_ID = os.environ.get('ECS_META_SEARCH_ACCESS_ID') or None
  ACCESS_KEY = os.environ.get('ECS_META_SEARCH_ACCESS_KEY') or None
  TOKEN = os.environ.get('ECS_META_SEARCH_TOKEN') or None
  ENDPOINT = os.environ.get('ECS_META_SEARCH_ENDPOINT') or None
  BUCKET = os.environ.get('ECS_META_SEARCH_BUCKET') or None
  HIDE_PASSWORD = os.environ.get('ECS_META_SEARCH_HIDE_PASSWORD') or False
