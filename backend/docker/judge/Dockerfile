ARG DAI_JUDGE_BASE_IMAGE=python:3.12-slim
FROM ${DAI_JUDGE_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Keep the disposable judge image byte-for-byte reproducible at the Python
# package layer.  A production build must still use a digest-pinned FROM.
RUN pip install --no-cache-dir \
    "pytest==8.3.4" \
    "numpy==2.1.3" \
    "pandas==2.2.3" \
    "scikit-learn==1.6.0"

WORKDIR /work
