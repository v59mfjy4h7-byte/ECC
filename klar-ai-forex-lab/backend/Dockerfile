FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 KLAR_DATA_DIR=/data
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY alembic ./alembic
COPY klar_lab ./klar_lab
EXPOSE 8000
CMD ["uvicorn", "klar_lab.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
