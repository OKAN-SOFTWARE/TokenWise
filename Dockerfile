FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . /app
RUN useradd --create-home --uid 10001 tokenwise && chown -R tokenwise:tokenwise /app
USER tokenwise
EXPOSE 8765
# Bind the Docker published port only to the host loopback interface.
CMD ["python", "-m", "tokenwise", "--host", "0.0.0.0", "--port", "8765"]
