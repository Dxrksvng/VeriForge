FROM python:3.13-alpine@sha256:1a63a53928ce53d2b0baf08092a703f4840ac5dfbd61fd48802dbf48e08c801e
# Target uses only the standard library. Remove unused installer/vendor packages.
RUN python -m pip uninstall --yes pip && python -c "import ensurepip,pathlib,shutil; shutil.rmtree(pathlib.Path(ensurepip.__file__).parent)"
WORKDIR /app
COPY policy.py /app/policy.py
COPY harness.py server.py /app/
USER 65534:65534
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "server.py"]
