# Quran Leerling Volgsysteem (Python + MariaDB + Docker)

Een eenvoudige website voor docenten om leerlingen te registreren met:
- naam van leerling
- huidige juz
- ayah waar ze bezig zijn
- datum en tijd
- goedkeurknop als een juz is afgerond

## Starten met Docker

1. Ga naar de projectmap.
2. Start alles:

```bash
docker compose up --build
```

3. Open de website op:
- http://localhost:5050

4. MariaDB extern bereikbaar op:
- localhost:3307

## Stoppen

```bash
docker compose down
```

## Data bewaren

MariaDB-data staat in een Docker volume (`mariadb_data`) en blijft bewaard na stoppen.

## Belangrijke bestanden

- `app.py`: Flask applicatie
- `templates/index.html`: webinterface
- `static/styles.css`: styling
- `db/init.sql`: database-init script
- `Dockerfile`: image voor webapp
- `docker-compose.yml`: start web + MariaDB samen
# quran
