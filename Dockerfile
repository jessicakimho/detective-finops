FROM python:3.13-slim

WORKDIR /app
COPY data/generator.py /app/data/generator.py

ENTRYPOINT ["python", "data/generator.py"]
CMD ["--output-dir", "/app/data/generated"]

