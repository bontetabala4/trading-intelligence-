# Image pour l'API FastAPI (broker_backend=mock ou bridge).
# Le backend "native" (MT5 réel) nécessite Windows et ne peut PAS tourner
# dans ce conteneur Linux — il doit être exécuté hors Docker sur une
# machine Windows avec le terminal MT5 installé, ou via le futur mode bridge.
FROM python:3.12-slim

WORKDIR /app

COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

COPY . .

EXPOSE 2026

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "2026"]
