# Klar AI Forex Lab

Lokal forskningsplattform för EUR/USD: data, backtest, forskning och paper trading med
**låtsaspengar**. Plattformen innehåller ingen kod för riktiga order (`LIVE_TRADING_ENABLED = False`
är hårdkodad och verifieras av test, liksom att ingen mäklar- eller nätverkskod finns).

Status: **M1 – fundament** (se [PLAN.md](PLAN.md) för arkitektur och milstolpar).

## Starta

### Med Docker (ett kommando)

```bash
cd klar-ai-forex-lab
docker compose up --build
```

Öppna <http://localhost:8080>. Data och databas sparas i `data/`.

### Utan Docker (två terminaler)

```bash
# Terminal 1 – backend (Python 3.11+)
cd klar-ai-forex-lab/backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn klar_lab.api.main:app --reload                 # http://localhost:8000/docs

# Terminal 2 – frontend (Node 18+)
cd klar-ai-forex-lab/frontend
npm install
npm run dev                                            # http://localhost:5173
```

Databasen migreras automatiskt vid start (Alembic). Manuellt: `alembic upgrade head` i `backend/`.

## Ladda data

På sidan **Marknad & data**:

- **Ladda upp CSV** med `time,open,high,low,close` (UTC), eller MT4/MT5-export med separata
  `Date`/`Time`-kolumner. Timdata (H1) rekommenderas.
- **Stora filer:** lägg dem i `data/incoming/` och importera därifrån (ingen uppladdningsgräns).
- **Syntetisk testdata** för att prova systemet. Den märks med banner överallt och i
  experimentregistret; resultat på den säger ingenting om verklig lönsamhet.

Varje import valideras. **Fel** gör att datasetet avvisas och ingenting sparas; **varningar**
sparas i valideringsrapporten och visas i UI.

| Kontroll | Grad |
|---|---|
| Saknade/ogiltiga priser, priser ≤ 0, high/low som inte omsluter open/close | fel |
| Priser utanför 0.5–2.0 (fel valutapar?) | fel |
| Samma tidsstämpel med olika priser | fel |
| Färre än 1 000 staplar, lucka längre än 7 dagar | fel |
| Identiska dubbletter (tas bort), osorterad data (sorteras) | varning |
| Luckor utöver normal helgstängning, rörelser > 2 % per stapel, många "platta" staplar | varning |

Samma data (samma SHA-256 efter normalisering) lagras bara en gång, oavsett filformat.

## Experimentregister

Varje körning sparar data-hash, kodversion (hash av källkoden, plus `GIT_SHA` om satt),
parametrar, slumpfrö, dataperiod (train/validation/test/full), mått och beslut med motivering.
Avslutade experiment och revisionsloggen kan **inte** ändras eller raderas (spärr på ORM-nivå,
verifierad av test). I M1 skapar varje dataimport ett `data_validation`-experiment.

## Tester

```bash
cd klar-ai-forex-lab/backend && python -m pytest -q     # 31 tester
cd klar-ai-forex-lab/frontend && npm run build          # typkontroll + bygge
```

Testerna täcker validering (varje regel), CSV-tolkning och hash, syntetisk data, registrets
oföränderlighet, API (uppladdning, avvisning, storleksgräns, path traversal vid import) och
säkerhetsreglerna.

## Hur resultat tolkas

M1 visar bara data och validering – inga strategiresultat. Från M2: alla mått är netto efter
kostnader, och varje graf/tabell märks med dataperiod (*in-sample*, *validering*, *test*).
Historiska resultat garanterar inte framtida resultat.

## Kända begränsningar (M1)

- Strategier, backtest, riskmotor, forskning och paper trading är inte byggda ännu; sidorna
  visar vilken milstolpe de kommer i.
- Prototypens fyra strategier gav på syntetisk data negativ förväntan efter kostnader i nästan
  alla perioder. Det är ingen slutsats om verklig data, men en påminnelse om att inget är bevisat.
- Ingen inloggning: avsett för en användare lokalt. Portarna binds bara till 127.0.0.1.
- Helgdetektering antar normal FX-stängning fredag→söndag/måndag (UTC); helgdagar redovisas som luckor.
- Grafen slår ihop staplar (OHLC bevaras) när datasetet har fler än 2 000 punkter.
- Docker-bygget kräver nätverksåtkomst till Docker Hub, PyPI och npm.
