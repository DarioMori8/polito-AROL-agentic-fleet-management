# Mock Backoffice

Espone via HTTP il workbook Q2 attraverso SQLite. Il database
`data/backoffice.db` è derivato dal file Excel e viene ricostruito automaticamente
all'avvio quando manca o quando il workbook è più recente.

## Avvio

```bash
cd mock-backoffice
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

## Endpoint

### Registro e dati commerciali

- `GET /machines`
- `GET /machines/{machine_id}`
- `GET /companies/{company_id}/orders`
- `GET /companies/{company_id}/quotes`

### Dati operativi / IoT

- `GET /machines/{machine_id}/health?window_hours=168` — quadro aggregato:
  ultimo snapshot, KPI, distribuzione degli stati e allarmi principali.
- `GET /machines/{machine_id}/telemetry` — snapshot orari con aggregati; filtri:
  `window_hours`, `from_timestamp`, `to_timestamp`, `operational_status`, `limit`.
- `GET /machines/{machine_id}/alarms` — eventi e conteggi; filtri:
  `window_hours`, `from_timestamp`, `to_timestamp`, `severity`, `status`,
  `alarm_code`, `limit`.
- `GET /machines/{machine_id}/maintenance-tickets` — ticket operativi; filtri:
  `from_date`, `to_date`, `status`, `priority`, `alarm_id`, `limit`.

Le finestre mobili finiscono all'ultimo snapshot della macchina, non a `now()`:
il dataset sintetico termina il 4 agosto 2026. I limiti evitano di inserire nel
contesto dell'LLM fino a 720 righe orarie. `machine_id` viene applicato prima di
ogni altro filtro e non può essere allargato dagli altri parametri.

La piattaforma non ha ancora autenticazione utente: il controllo `companyId` +
`visibility` descritto nel README del dataset dovrà essere applicato nel backend
quando sarà disponibile un'identità autenticata. Il solo filtro macchina non è
un sostituto dell'autorizzazione.

La documentazione OpenAPI interattiva è su `http://localhost:8003/docs`.
