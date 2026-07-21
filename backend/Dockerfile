FROM python:3.12-slim

WORKDIR /app

# libmagic1: shared library python-magic binds to for real content sniffing
# (not just trusting the client's Content-Type header or filename extension).
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# unstructured's docx/pptx text-classification heuristics need these two NLTK
# resources. unstructured tries to fetch them from its own S3 mirror at
# runtime if missing, and that mirror currently 403s — pre-installing via
# NLTK's own (reliable) downloader means unstructured's check finds them
# already present and never touches the broken URL.
ENV NLTK_DATA=/usr/local/share/nltk_data
RUN python -m nltk.downloader -d /usr/local/share/nltk_data punkt_tab averaged_perceptron_tagger_eng

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
