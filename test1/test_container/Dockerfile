FROM python:3.8
COPY requirements.txt /requirements.txt
WORKDIR /
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app
EXPOSE 5000
CMD ["gunicorn", "--workers=1", "-b 0.0.0.0:5000", "--log-level=debug", "service_env:app"]