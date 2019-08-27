BASE_DIR: $base_dir
UPLOADS_DIR: ./media/uploads
JOBS_DIR: ./media/jobs
LOG_DIR: ./logs
SERVICES: ./services.yml

UPLOADS_URL_PATH: /media/uploads
JOBS_URL_PATH: /media/jobs

ACCEPTED_MEDIA_TYPES:
  - text/plain

SERVER_HOST: 127.0.0.1
SERVER_PORT: 8000

SLIVKA_QUEUE_ADDR: 127.0.0.1:3397
SECRET_KEY: $secret_key

MONGODB_ADDR: 127.0.0.1:27017
