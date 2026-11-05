FROM python:3.14-slim AS builder
WORKDIR /build
COPY requirements.txt requirements-dev.txt ./
RUN pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements-dev.txt

FROM python:3.14-slim AS runtime
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt
RUN useradd --create-home --uid 10001 appuser
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
COPY requirements-dev.txt ./
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    pip install --no-cache-dir --no-index --find-links=/wheels -r requirements-dev.txt
COPY tests ./tests
COPY pytest.ini ./
USER appuser
CMD ["python", "-m", "pytest", "-v", "-p", "no:cacheprovider"]

FROM runtime AS production
