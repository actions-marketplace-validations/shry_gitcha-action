FROM python:3.9-slim-buster as python-base


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1  \
    PYSETUP_PATH=/opt/pysetup \
    VENV_PATH=/opt/pysetup/.venv 

# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

FROM python-base as builder-base

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        build-essential \
        gcc

# install poetry - respects $POETRY_VERSION & $POETRY_HOME
RUN curl -sSL https://install.python-poetry.org | python

# copy project requirement files here to ensure they will be cached.
WORKDIR $PYSETUP_PATH
COPY poetry.lock pyproject.toml README.md ./
COPY gitcha/ ./gitcha

RUN poetry install --only main

FROM python-base as final
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH


ENTRYPOINT ["python3", "/opt/pysetup/gitcha/main.py"]
