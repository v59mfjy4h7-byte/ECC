# Klar AI Forex Lab

Lokal forskningsplattform för EUR/USD: data, backtest, forskning och paper trading med
**låtsaspengar**. Plattformen innehåller ingen kod för riktiga order (`LIVE_TRADING_ENABLED = False`
är hårdkodad och verifieras av test, liksom att ingen mäklar- eller nätverkskod finns).

Status: **M2 – backtest + risk** klar (se [PLAN.md](PLAN.md) för arkitektur och milstolpar).

## Starta

### Med Docker Desktop (enklast)

1. Starta Docker Desktop och vänta tills det står **Engine running**.
2. Dubbelklicka på `start-windows.bat` (Windows) eller `start-mac.command` (Mac) i mappen
   `klar-ai-forex-lab`. Första gången tar bygget några minuter; sedan öppnas <http://localhost:8080>.
3. Därefter startar och stoppar du labbet under **Containers** i Docker Desktop.

Från en terminal i mappen `klar-ai-forex-lab` går det också: `docker compose up -d --build`.
Data och databas sparas i `data/`.

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

## Backtest och risk (M2)

På sidan **Strategier** körs agent A–D (trend, momentum, mean reversion, breakout) på aktivt dataset.
Datan delas kronologiskt: träning 60 % (efter 250 staplars uppvärmning), validering 20 %, test 20 %.

- **Motorn:** signal på stapel *i* → order på öppningen av *i+1*. Spread, slippage, provision och
  swap (rollover 22:00 UTC, onsdag ×3) dras. Nås stop och TP i samma stapel antas stop. Gap förbi
  stop fylls på öppningen (sämre), gap förbi TP fylls på TP (aldrig bättre).
- **Riskmotorn** (eget paket, strategierna får inte importera det): 1 % risk per affär, netto-RR
  ≥ 2, 3 % daglig förlustgräns, permanent stopp vid 20 % nedgång, hävstång ≤ 10, max en position,
  dubbelorderskydd, föråldrade data, orimliga priser och kill switch. Varje avvisad order sparas med orsak.
- **Testperioden är låst.** Den öppnas bara på uttrycklig begäran, en gång per strategikonfiguration
  och dataset, och öppningen loggas.
- **Kill switch:** knappen i UI eller filen `data/STOP` stoppar alla nya affärer omedelbart.
- **Riskgränser** ändras bara via signerad fil (se sidan Inställningar). Även en signerad fil får
  bara skärpa specifikationens gränser; en manipulerad fil spärrar alla backtester.
- **Kontroll mot prototypen:** utan swap ger porten exakt prototypens antal affärer och avkastning
  för validerings- och testperioden (låst av ett regressionstest).

## Experimentregister

Varje körning sparar data-hash, kodversion (hash av källkoden, plus `GIT_SHA` om satt),
parametrar, slumpfrö, dataperiod (train/validation/test/full), mått och beslut med motivering.
Avslutade experiment och revisionsloggen kan **inte** ändras eller raderas (spärr på ORM-nivå,
verifierad av test). Varje dataimport skapar ett `data_validation`-experiment och varje
backtest ett `backtest`-experiment med strategi, parametrar, konfigurationshash och full riskkonfiguration.
Affärer, beslut och equity-kurva sparas i `data/runs/<id>/`.

## Tester

```bash
cd klar-ai-forex-lab/backend && python -m pytest -q     # 82 tester
cd klar-ai-forex-lab/frontend && npm run build          # typkontroll + bygge
```

Testerna täcker validering (varje regel), CSV-tolkning och hash, registrets oföränderlighet,
varje riskregel, motorns order-/kostnads-/gap-/swapregler, strategiernas kausalitet och
parametervalidering, att strategier inte kan importera riskmotorn, signerad konfiguration,
låst testperiod, kill switch, API och säkerhetsreglerna.

## Hur resultat tolkas

- Alla mått är netto efter kostnader. Varje graf/tabell märks med dataperiod (*in-sample*, *validering*, *test*).
- Förväntat/affär > 0 och profit factor > 1 i **alla** perioder är ett minimikrav, inte ett bevis.
  Hög vinstprocent räcker aldrig.
- ⚠ = färre än 30 affärer (för svagt underlag). ■ = kontot stoppades vid 20 % nedgång.
- Ju fler konfigurationer som testas, desto större risk att någon ser lönsam ut av slump.
  M3 räknar alla och korrigerar för det.
- Historiska resultat garanterar inte framtida resultat.

## Kända begränsningar

- Optimering, walk-forward, robusthetstester, Agent E och paper trading är inte byggda ännu (M3–M5).
- Backtester körs synkront i anropet (~2 s för 30 000 staplar × 4 strategier); jobbkö kommer i M3.
- På syntetisk data har alla fyra strategier negativ förväntan efter kostnader och når 20 %-stoppet
  i träningsperioden. Det säger inget om verklig data, men inget är bevisat lönsamt.
- Swap ingår inte i planerad risk per affär; en position som hålls många nätter kan förlora något
  mer än 1 %. Gap förbi stop kan också ge större förlust än planerat (redovisas per affär).
- Kill switch kontrolleras vid varje orderbeslut. Affärer som redan är öppna stängs inte automatiskt.
- Ingen inloggning: avsett för en användare lokalt. Portarna binds bara till 127.0.0.1.
- Helgdetektering antar normal FX-stängning fredag→söndag/måndag (UTC); helgdagar redovisas som luckor.
- Grafer slår ihop punkter när de är fler än 2 000 (OHLC bevaras för pris).
- Docker-bygget kräver nätverksåtkomst till Docker Hub, PyPI och npm.
