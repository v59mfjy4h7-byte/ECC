# Klar AI Forex Lab – plan

Lokal forskningsplattform där en AI-agent lär sig vilka EUR/USD-strategier och marknadslägen som
fungerar, via ett kontrollerat forskningsflöde. Låtsaspengar på riktiga data. **Ingen livehandel byggs.**

## Arkitektur

| Del | Val | Motivering |
|---|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, SQLite, pandas/NumPy | Enligt master-prompten; SQLite räcker lokalt, Alembic ger migrationer |
| Frontend | React 18 + Vite + TypeScript + Tailwind, Lightweight Charts | Enligt master-prompten; equity-kurvor ritas också med Lightweight Charts (inget extra beroende) |
| Drift | `docker compose up` (backend + nginx som serverar frontend och proxar `/api`) | Ett kommando; portar binds bara till 127.0.0.1 |
| Jobb (M3) | Egen enkel kö i backend (tråd/process + status i DB), avbrytbar | Inga extra tjänster (Redis/Celery) förrän behov visas |

```text
klar-ai-forex-lab/
  backend/
    klar_lab/
      settings.py        LIVE_TRADING_ENABLED=False (hårdkodad), sökvägar
      db.py, models.py   SQLite + Alembic-migrationer (alembic/versions)
      data/              DataFeed-gränssnitt, CsvFeed, SyntheticFeed, validering
      registry.py        experimentregister + revisionslogg (oföränderliga)
      datasets.py        import/lagring/nedsampling av dataset
      api/main.py        REST-API
      risk/              riskmotor + signerad riskkonfiguration (strategier får inte importera den)
      engine/            backtestmotor (portad), mått, train/val/test-uppdelning
      strategies/        A–D bakom deklarativt Strategy-interface
      research/          kör backtester som experiment; låst testperiod
                (M3–M4) + Optuna, walk-forward, robusthet, DSR, Agent E, regimer, meta-modell
      paper/     (M5)    PaperLiveFeed, paper-motor, drift-övervakning
    tests/
  frontend/src/          sidor: Översikt, Marknad & data, Strategier, Forskning, Paper, Risk & logg, Inställningar
  data/                  SQLite-DB, normaliserade dataset (<sha256>.csv), incoming/
```

## Milstolpar

| | Innehåll | Klar när | Status |
|---|---|---|---|
| **M1** | Projekt, DB + migrationer, FastAPI, React-skelett, CsvFeed, validering, experimentregister | `docker compose up` visar dashboard med laddad data | **Klar** |
| **M2** | Backtest- och riskmotor portade från prototypen med full testsvit; A–D körs och visas i UI | Prototypens tester + nya passerar, resultat per period i UI | **Klar** |
| M3 | Optuna (endast träning), walk-forward per fönster, robusthet, Deflated Sharpe, befordringstrappa, jobbkö | Spärrarna testade; varje konfiguration räknas | Nästa |
| M4 | Agent E (deklarativa hypoteser), regimdetektor, meta-modell med "avstå" | Agent E kan inte köra godtycklig kod (test) | |
| M5 | PaperLiveFeed, paper-motor, drift (CUSUM), kill switch i UI | Paper-utfall jämförs mot backtestförväntan | |
| M6 | (valfri) RL i Gymnasium, samma pipeline | | |

## Antaganden (säkra standardval)

- Specifikationen "KLAR AI FOREX AGENT v1.0" fanns inte med; prototypen (`klar_ai_forex/`) och
  master-prompten används som källa. Prototypens regler (1 % risk, netto-RR ≥ 2, 3 % daglig
  förlustgräns, 20 % maxnedgång, kostnadsmodell) är portade oförändrade (M2).
- Swap (ny i M2) är ett konservativt antagande: kostnad åt båda håll (0.5/0.3 pips per natt, onsdag ×3).
- Gap förbi take profit fylls på TP, inte på det bättre öppningspriset (prototypen gav öppningspriset).
- Alla tider är UTC. Tidszonsmärkta tider konverteras; omärkta antas vara UTC.
- Staplar tolkas som bid-priser (som i prototypen).
- Samma data identifieras av SHA-256 av den normaliserade CSV:n, oberoende av ursprungsformat.
- En enda användare, lokalt. Ingen inloggning; API:t exponeras bara på 127.0.0.1.

## Risker

- **Överanpassning** är den största risken. Motåtgärd: sökning bara på träning, val på validering,
  låst test, alla konfigurationer räknas och korrigeras (M3).
- **Datakvalitet:** gratis-CSV kan ha luckor/fel tidszon. Motåtgärd: valideringen redovisar allt, fel avvisar.
- **Lookahead-buggar:** Motåtgärd: kausalitetstester för varje strategi och motorregel (M2).
- **Kostnadsmodellen** (spread/slippage) är ett antagande; stresstest med 2× kostnad i M3.
- **Säkerhet:** inga hemligheter i koden; mäklar-/nätverkskod förbjuds av test i M1–M4. PaperLiveFeed
  (M5) blir den enda nätverkskoden och isoleras i en egen modul utan orderfunktioner.
