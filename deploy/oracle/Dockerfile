FROM python:3.12-slim-bookworm

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .

ENV JH_API_BACKEND=ollama
ENV JH_OLLAMA_URL=http://ollama:11434

EXPOSE 8080
CMD ["python", "-m", "safety_eval.platform.serve", "--host", "0.0.0.0", "--port", "8080"]
