FROM python:3.12-slim

ARG MODULE_DIR
ARG MODULE_APP
ARG PORT=8000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    MODULE_APP=${MODULE_APP} \
    PORT=${PORT}

WORKDIR /srv

# Packages every module needs (the api.py files use these)
COPY docker/module-base-requirements.txt /tmp/base.txt
RUN pip install --no-cache-dir -r /tmp/base.txt

# Then the module's own packages, if it has a requirements.txt
COPY ${MODULE_DIR}/ /srv/${MODULE_DIR}/
RUN if [ -f /srv/${MODULE_DIR}/requirements.txt ]; then \
    pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -r /srv/${MODULE_DIR}/requirements.txt; \
    fi

COPY shared/ /srv/shared/

EXPOSE ${PORT}
CMD ["sh", "-c", "uvicorn $MODULE_APP --host 0.0.0.0 --port $PORT"]