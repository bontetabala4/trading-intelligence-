# ATIP Web

Client Next.js V1 pour l’analyse et le paper trading. Il consomme exclusivement l’API FastAPI ; il ne peut pas déclencher d’ordre réel.

```bash
npm install
copy .env.local.example .env.local
npm run dev
```

Définissez `NEXT_PUBLIC_API_BASE_URL=http://localhost:2026` si l’API n’est pas sur cette adresse. L’interface affiche explicitement le mode analyse/mock retourné par le backend.
