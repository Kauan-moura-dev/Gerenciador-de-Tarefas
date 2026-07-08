FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY app.py .

# O banco fica em /dados (volume no docker-compose) para sobreviver a recriações
ENV BANCO_DADOS=/dados/tarefas.db

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
