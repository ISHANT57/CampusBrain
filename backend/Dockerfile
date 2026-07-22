FROM python:3.12-slim

WORKDIR /app

# libmagic1: python-magic's content-sniffing library.
# libgl1/libglib2.0-0: opencv (PaddleOCR's dependency) needs these on slim Debian.
# libgomp1: paddlepaddle's compiled core is linked against OpenMP and won't import without it.
# fonts-dejavu-core: lets test fixtures render real, OCR-legible text.
# libreoffice: unstructured's doc/ppt/xls[legacy binary Office] extras shell
# out to `soffice` to convert those formats before parsing them — added for
# .doc/.ppt/.xls support (upload_policy.py). NOT build-verified (no local
# Docker daemon while writing this) and it's a large package — expect a real
# image-size and cold-start increase on Render's free tier. If that cost
# isn't worth 3 file formats, drop this line and remove .doc/.ppt/.xls from
# upload_policy.py's SUPPORTED_TYPES instead.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 libgl1 libglib2.0-0 libgomp1 fonts-dejavu-core libreoffice \
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
