FROM python:3.14-slim

ENV PYTHONDONTWRITEBYCODE = 1 \ PYTHONUNBUFERED = 1


WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent.py app.py ./

RUN useradd --create-home appuser
USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]


