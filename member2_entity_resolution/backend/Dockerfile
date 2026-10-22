FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/srv/member2/.hf
WORKDIR /srv/member2/backend
COPY backend/requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('sentence-transformers/all-MiniLM-L6-v2')"
COPY backend/app ./app
COPY schemas /srv/member2/schemas
EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]