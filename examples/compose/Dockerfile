# Version tags are explicit, not immutable. See README for digest pinning.
ARG PYTHON_IMAGE=python:3.12.15-slim-bookworm
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/nova
COPY django-theme/ /opt/nova/django-theme/
COPY examples/compose/ /opt/nova/examples/compose/
ARG WITH_CAPTCHA=0
RUN python -m pip install --no-cache-dir -r examples/compose/requirements.txt \
    && if [ "$WITH_CAPTCHA" = "1" ]; then \
         python -m pip install --no-cache-dir './django-theme[captcha]'; \
       elif [ "$WITH_CAPTCHA" = "0" ]; then \
         python -m pip install --no-cache-dir ./django-theme; \
       else exit 2; fi \
    && python -m pip check
WORKDIR /opt/nova/django-theme/demo
USER 1000:1000
CMD ["python", "/opt/nova/examples/compose/start.py"]

