FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /retail_ai_assistant_app

RUN rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser

# Give ownership of the /retail_ai_assistant_app directory to appuser
RUN chown -R appuser:appuser /retail_ai_assistant_app

# Switch to the non-root user
USER appuser

HEALTHCHECK CMD wget --no-verbose --tries=1 --spider http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
