"""Production WSGI entrypoint: exactly one worker owns the YOLO model."""
from server import app, service

service.initialize()
