# Notifications

ATIP n’envoie aucune notification par défaut. Le provider par défaut est explicitement désactivé ; une livraison échouée n'affecte jamais la décision analytique ni ne déclenche une action de trading.

## SMTP optionnel

Configurez ces variables hors Git pour activer l’adaptateur SMTP :

```text
NOTIFICATION_EMAIL_ENABLED=true
NOTIFICATION_SMTP_HOST=smtp.example.com
NOTIFICATION_SMTP_PORT=587
NOTIFICATION_SMTP_USERNAME=...
NOTIFICATION_SMTP_PASSWORD=...
NOTIFICATION_SMTP_FROM=alerts@example.com
NOTIFICATION_SMTP_STARTTLS=true
```

Quand la configuration est absente ou incomplète, ATIP utilise `DisabledNotificationAdapter` et enregistre un échec de livraison explicite. Le connecteur SMTP a un timeout de dix secondes, n'écrit jamais le mot de passe dans les logs et n'envoie aucun ordre.

La déduplication actuelle est en mémoire dans `NotificationService`. Sa persistance et les retries via worker restent des travaux de phase 3 ; elle ne doit donc pas être considérée comme résistante à un redémarrage.
