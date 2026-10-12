FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssl postgresql-client \
    && rm -rf /var/lib/apt/lists/*
COPY prepare.py /prepare.py
ENTRYPOINT ["python", "/prepare.py"]
