FROM python:3.11-slim
LABEL authors="edwardgarcia"
WORKDIR /carciscan

RUN apt-get update \
    && apt-get -y install libpq-dev gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /carciscan/requirements.txt
RUN pip install --no-cache-dir -r /carciscan/requirements.txt
COPY ./app /carciscan/app
COPY entrypoint.sh /carciscan/entrypoint.sh
RUN chmod +x /carciscan/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/carciscan/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
