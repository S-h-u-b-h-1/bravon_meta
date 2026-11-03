FROM python:3.12-alpine@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d
WORKDIR /service
COPY server.py /service/server.py
ENV PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8080
CMD ["python", "/service/server.py"]
