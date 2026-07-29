# Mock Backoffice

Finge di essere l'ERP/CRM/Document Store reale di AROL (vedi slide 8/9 della presentazione: "ERP MCP", "CRM MCP", "Document Store"). Espone via HTTP gli stessi dati che, in produzione, arriverebbero da sistemi come SAP o Salesforce — così `docs_agent` (e in futuro `orders_agent`) parlano con un vero endpoint HTTP invece di leggere un file locale, ed è più semplice sostituirlo in seguito con l'integrazione reale (basta cambiare `DOCS_SERVICE_URL` e aggiungere l'autenticazione).

## Avvio

```bash
cd mock-backoffice
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

## Endpoint

- `POST /documents/search` — body `{"query": str, "machine_id": str, "document_type": str | null, "order_id": str | null}` → `{"results": [Document, ...]}`
- `GET /orders?machine_id=...&order_id=...&status=...&order_type=...` → `{"results": [Order, ...]}`
- `GET /quotes?machine_id=...&quote_id=...&status=...` → `{"results": [Quote, ...]}`

`machine_id` è obbligatorio ovunque ed è applicato per primo: è il confine di controllo accessi, quindi nessuna combinazione di filtri può restituire dati di un'altra macchina. Gli altri filtri sono opzionali.

I dati sono in `data/*.json`, tutti riferiti all'unica macchina mock (`machine_id = "generic"`).
