# AROL Fleet Management — guida per la consegna

## Avvio rapido per il docente

1. **Installare e aprire [Docker Desktop](https://www.docker.com/products/docker-desktop/)**. Su Linux va bene anche Docker Engine con Docker Compose v2. Attendere che Docker risulti avviato.
   Verificare di aver assegnato a Docker **almeno 16 GB di RAM**. Nelle installazioni che mostrano il limite in Docker Desktop: **Settings → Resources → Advanced → Memory**, quindi applicare e riavviare. Con WSL2 la memoria della macchina virtuale si configura nelle impostazioni WSL. La RAM totale del computer e quella assegnata a Docker sono due valori diversi.
2. **Estrarre tutto il pacchetto ZIP** in una cartella locale. I PDF devono essere già presenti in `data/manuals/`.
3. **Avviare il progetto**:
   - **Windows:** doppio clic su `avvia.bat` nella cartella estratta.
   - **macOS/Linux:** aprire il terminale nella cartella estratta ed eseguire `sh avvia.sh`.
4. Attendere il messaggio **Pronto**, poi aprire **[http://localhost:8080](http://localhost:8080)**.

Credenziali dell'applicazione:

| Campo | Valore |
|---|---|
| Email | `elena.fabbri@valgrande.example` |
| Password | `Arol2026!` |

Non occorre installare Python, Node.js o Ollama sul computer, né creare un file `.env`, account cloud o chiavi API. È necessario Internet durante il primo avvio per scaricare immagini, dipendenze e modelli. Le successive inferenze e ricerche nei manuali avvengono localmente.

**Il primo avvio può richiedere parecchi minuti**, soprattutto per il download e l'indicizzazione. Il tempo dipende da connessione, CPU e memoria. Non chiudere Docker durante la preparazione. Gli script attendono fino a due ore; se l'attesa scade, controllare i log prima di rilanciarli.

## Requisiti del computer

- Docker Desktop aggiornato oppure Docker Engine con Compose v2, su architettura x86-64 o ARM64.
- Budget consigliato per l'intero stack: **almeno 16 GB di RAM assegnati a Docker**, quindi preferibilmente un computer con 24–32 GB di RAM. È una stima prudenziale, non un minimo certificato su ogni hardware.
- Prevedere **circa 25 GB di spazio libero** per immagini, modelli, cache di compilazione e dati; l'uso può crescere con le conversazioni e le tracce.
- Porte **8080** e **3000** libere sul computer.

Le immagini dei servizi infrastrutturali sono fissate tramite digest nel file Compose, per riutilizzare le versioni collaudate.

La configurazione standard usa la CPU ed evita di richiedere driver GPU. Su CPU le risposte, che possono comportare più chiamate al modello, possono richiedere minuti. Su macOS Docker non espone l'accelerazione Metal a Ollama: per una demo più veloce su Mac è disponibile anche l'ambiente di sviluppo con Ollama nativo, descritto nel [README](README.md). [Riferimento Ollama](https://docs.ollama.com/faq).

**Attenzione ai tempi della demo:** nel collaudo su Mac ARM64 con 16 GB assegnati a Docker, una domanda sul manuale ha richiesto circa **19 minuti** per la risposta completa. È una misura di quel computer, non una previsione per ogni CPU. Per una presentazione interattiva è preferibile una macchina con accelerazione GPU compatibile; effettuare una prova sul computer del docente prima della consegna.

## Cosa viene preparato automaticamente

Il pacchetto usa **Docker Compose** per avviare un insieme coordinato di container. Il docente esegue un solo comando o script.

1. Costruzione delle immagini di frontend, backend, agenti e mock backoffice.
2. Avvio del mock backoffice e caricamento del dataset Excel incluso nel repository.
3. Avvio di Ollama all'interno di Docker.
4. Verifica della presenza dei manuali di tutte le otto macchine.
5. Download di **`llama3.1:8b`**, usato dall'orchestratore e dagli agenti, e **`nomic-embed-text`**, usato per gli embedding. I modelli già presenti vengono riutilizzati.
6. Estrazione del testo dei PDF, suddivisione in frammenti e costruzione dell'indice Chroma.
7. Avvio di Langfuse e dei suoi servizi; creazione automatica di organizzazione, progetto, account e chiavi API.
8. Prova reale di generazione di un token, con la stessa finestra di contesto della chat: verifica che il modello riesca a caricarsi in memoria. Il modello viene poi scaricato dalla RAM, mantenendo i pesi nel volume.
9. Avvio di agenti, backend e interfaccia, in quest'ordine e solo dopo la riuscita dei passaggi necessari.

Il modello scelto è la variante Llama 3.1 da 8 miliardi di parametri con supporto alle chiamate di strumenti; il download del modello è circa 4,9 GB. [Scheda ufficiale](https://ollama.com/library/llama3.1:8b).

Il servizio `setup` termina con **`Exited (0)`** quando ha finito: è il comportamento corretto. Un errore durante download, ingestion o prova di generazione impedisce l'avvio degli agenti e dell'interfaccia. Gli script mostrano anche gli ultimi messaggi di setup in caso di errore. Durante il collaudo, con circa 8 GB assegnati a Docker, il sistema ha terminato Llama per memoria insufficiente: non basta vedere i container attivi per sapere che la chat può funzionare.

## Prima prova

Dopo il login:

1. Aprire una macchina della flotta visibile all'utente.
2. Provare una domanda sul manuale, per esempio: **«Quali controlli di manutenzione sono previsti per questa macchina?»**
3. Verificare le fonti citate e l'apertura del PDF.
4. Provare una domanda operativa, per esempio: **«Quali allarmi recenti risultano per questa macchina?»**

Il dataset operativo è sintetico e termina il **4 agosto 2026**: le finestre temporali recenti sono riferite all'ultimo dato della macchina.

| Servizio | Indirizzo / accesso |
|---|---|
| Applicazione | [localhost:8080](http://localhost:8080) |
| Stato API | [localhost:8080/api/health](http://localhost:8080/api/health) |
| Langfuse | [localhost:3000](http://localhost:3000) |
| Login Langfuse | `docente@arol.local` / `ArolDemo2026!` |
| Progetto Langfuse | `AROL Fleet Management` |

Dopo una domanda, le tracce compaiono in Langfuse con un breve ritardo. Account, progetto e chiavi sono creati tramite l'[inizializzazione automatica di Langfuse](https://langfuse.com/self-hosting/administration/headless-initialization).

Questa configurazione è destinata alla **demo locale**: usa credenziali dimostrative dichiarate e pubblica l'app e Langfuse soltanto su `127.0.0.1`. Gli altri servizi rimangono nella rete Docker. Non è una configurazione per pubblicare il servizio su Internet.

## Fermare e riavviare

Tutti i comandi seguenti vanno eseguiti nella cartella estratta.

**Fermare il progetto**, mantenendo modelli, indice, conversazioni e tracce:

```sh
docker compose -f compose.delivery.yml down
```

**Riavviare:** eseguire di nuovo `avvia.bat` oppure `sh avvia.sh`. Gli script fermano prima i servizi che leggono Chroma, poi ripetono i controlli e attendono che l'app sia pronta. I PDF invariati e i modelli già scaricati vengono riutilizzati.

È possibile avviare direttamente con Compose, a stack fermo:

```sh
docker compose -f compose.delivery.yml up --build --wait --wait-timeout 7200
```

Per un riavvio senza ricostruire immagini già preparate, anche senza Internet:

```sh
docker compose -f compose.delivery.yml up --wait --wait-timeout 7200 --pull never --no-build
```

Quest'ultimo comando richiede che il primo avvio sia già terminato con successo e che non siano stati cambiati i modelli richiesti.

**Vedere lo stato:**

```sh
docker compose -f compose.delivery.yml ps -a
```

**Seguire la preparazione** da un secondo terminale, dopo che il container `setup` è stato creato:

```sh
docker compose -f compose.delivery.yml logs -f setup
```

**Vedere i log dell'applicazione:**

```sh
docker compose -f compose.delivery.yml logs --tail 100 backend agents
```

## Manuali e persistenza

I PDF originali si trovano in `data/manuals/` e sono montati in sola lettura. Non spostare o eliminare la cartella estratta mentre il progetto è in uso.

I volumi Docker conservano separatamente modelli Ollama, indice Chroma, database dell'applicazione, dataset caricato e dati Langfuse. Sono isolati dall'ambiente di sviluppo dal nome di progetto `arol-delivery`. Un normale `down` non li cancella.

L'ingestion registra il completamento di ogni PDF soltanto dopo aver salvato tutti i frammenti. Se viene interrotta, al riavvio recupera i manuali incompleti; quelli invariati vengono saltati. Un PDF cambiato viene reindicizzato; cambiare il modello di embedding ricostruisce l'indice.

Per aggiornare i manuali, fermare lo stack, sostituire i PDF mantenendo i nomi previsti e riavviare con lo script. Il pacchetto richiede almeno un manuale per ciascuna delle otto macchine.

**Reset completo, solo se si vogliono cancellare tutti i dati della demo:**

```sh
docker compose -f compose.delivery.yml down --volumes
```

Questo elimina anche i modelli scaricati, le conversazioni e le tracce. Al successivo avvio occorrerà rifare download e ingestion. I PDF nella cartella restano presenti.

## GPU NVIDIA opzionale

Su un computer con GPU NVIDIA e ambiente Docker già configurato per usarla, avviare da stack fermo con:

```sh
docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml up --build --wait --wait-timeout 7200
```

Il file aggiuntivo assegna la GPU al solo container Ollama. Su Linux servono i driver e NVIDIA Container Toolkit; la configurazione è descritta nella [documentazione Ollama per Docker](https://docs.ollama.com/docker) e nella [guida Docker Compose per le GPU](https://docs.docker.com/compose/how-tos/gpu-support/). Non usare questa variante su Mac o su computer senza NVIDIA. Per mantenere la GPU ai successivi avvii riutilizzare questo comando, preceduto da `docker compose -f compose.delivery.yml down`.

## Risoluzione dei problemi

| Problema | Soluzione |
|---|---|
| Docker non risponde | Aprire Docker Desktop e attendere che il motore sia pronto. Su Linux avviare Docker Engine. |
| Porta già occupata | Fermare l'altra applicazione o lo stack di sviluppo che usa 8080/3000. |
| `setup` termina con errore | Leggere `docker compose -f compose.delivery.yml logs setup`. Correggere la causa e rilanciare lo script. |
| `Missing manuals`, `No PDF manuals` o cartella non trovata | Verificare che lo ZIP sia stato estratto interamente e contenga tutti i PDF in `data/manuals/`. |
| Nome PDF non valido o seriale sconosciuto | Ripristinare il nome originale `<seriale>_manual_EN.pdf`. |
| Download interrotto | Ripristinare la connessione e rilanciare lo script. I dati già scaricati rimangono nel volume Ollama. |
| Preparazione apparentemente ferma | Seguire i log di `setup`; l'indicizzazione può durare a lungo su CPU. |
| Container terminato con codice 137, errore di memoria o chat molto lenta | Aumentare la memoria disponibile a Docker e chiudere applicazioni pesanti; usare la variante GPU se disponibile. |
| App attiva ma risposta molto lenta | Su CPU sono possibili più minuti per domanda. Controllare i log di `backend`, `agents` e `ollama`. |
| Risposta incompleta o strumenti scelti male | Llama 3.1 8B è un modello locale compatto; le risposte vanno verificate sulle fonti e non ne è garantita la correttezza. |
| Interfaccia precedente rimasta nel browser | Ricaricare la pagina; se necessario cancellare i dati del sito/PWA per `localhost:8080`. |

Per diagnosi avanzata, verificare i modelli installati:

```sh
docker compose -f compose.delivery.yml exec ollama ollama list
```

Le impostazioni opzionali `DELIVERY_LLM_MODEL`, `DELIVERY_EMBEDDING_MODEL`, `DELIVERY_NUM_CTX`, `DELIVERY_APP_PORT` e `DELIVERY_LANGFUSE_PORT` possono essere definite nell'ambiente del terminale prima dell'avvio. I valori predefiniti non richiedono configurazione. Un modello alternativo per la chat deve supportare il tool calling e deve entrare nella memoria disponibile.

## Preparazione del pacchetto — per il gruppo di progetto

Questa sezione non richiede attività al docente.

I manuali AROL non sono versionati in Git. Prima della consegna devono essere inclusi nello ZIP riservato al corso:

```text
data/manuals/
  15610_manual_EN.pdf
  17203_manual_EN.pdf
  17478_manual_EN.pdf
  17579_manual_EN.pdf
  A2055_manual_EN.pdf
  A2064_manual_EN.pdf
  A2132_manual_EN.pdf
  A4344_manual_EN.pdf
```

Dalla copia di lavoro completa del repository, generare il pacchetto con:

```sh
python3 scripts/package_delivery.py
```

Il risultato è **`dist-delivery/arol-fleet-management.zip`**: contiene i sorgenti correnti, il dataset Excel, gli script, questa guida e gli otto PDF. Esclude file `.env` personali, database, indici locali, ambienti Python e `node_modules`. Il pacchetto va rigenerato dopo le ultime modifiche ai sorgenti.

Consegnare questo ZIP attraverso il canale riservato del corso. I manuali sono materiale AROL e non vanno aggiunti al repository pubblico. Il pacchetto non contiene le immagini Docker o i pesi del modello: vengono scaricati al primo avvio.

Prima della consegna definitiva, provare lo ZIP su una macchina con risorse adeguate, verificando login, una risposta con fonti dal manuale, una domanda sui dati operativi e una traccia in Langfuse. La qualità delle risposte di Llama 3.1 8B va verificata sul computer usato per la dimostrazione.

### Collaudo del pacchetto (25 ottobre 2026)

Ambiente provato: macOS ARM64, 32 GB di RAM fisica, Docker configurato con 16 GB, inferenza su CPU.

- Avvio tramite `sh avvia.sh` completato; tutti i servizi applicativi risultano pronti.
- Download reale dei due modelli e ingestion di **8 manuali / 2.155 frammenti** completati. Al riavvio vengono riutilizzati.
- Controllo iniziale di generazione, login, elenco delle macchine e apertura del PDF dal browser verificati.
- Traccia reale dell'orchestratore presente nel progetto Langfuse creato automaticamente.
- **39 test selezionati passati**: 29 per agenti/ingestion/bootstrap, 5 per backend e 5 per mock backoffice. I test già presenti in `agents/tests/test_agent_failures.py` hanno errori e non sono compresi in questi 39: non si dichiara superata l'intera suite.
- ZIP estratto e immagini ricostruite con successo dalla copia estratta: contiene gli otto PDF e i sorgenti aggiornati, senza file `.env` personali.
- Chat completa sul manuale verificata attraverso il frontend: risposta in italiano e cinque citazioni alle pagine PDF **95, 129 e 133**, in **1.136,8 secondi (circa 19 minuti)**. Il PDF è stato aperto nel browser anche alla pagina 95.
- Accesso reale ai dati operativi verificato tramite il client dell'agente: per `MCH-0001`, nella finestra 29 luglio–4 agosto 2026, sono presenti 14 allarmi. La seconda prova di chat sugli allarmi è stata interrotta dopo l'avvio; non si dichiara verificata la sua risposta finale con Llama.

**Limiti emersi nella prova del modello:** per un semplice saluto, Llama 3.1 8B ha impiegato circa 7 minuti per la prima decisione e ha chiamato erroneamente `search_iot` con una domanda vuota. Questa prova è stata interrotta. La risposta sul manuale è arrivata con fonti pertinenti, ma contiene difetti di traduzione e formattazione. L'installazione riuscita e i test automatici non certificano la qualità delle risposte del modello: questa versione 8B richiede una verifica dei contenuti prima della dimostrazione.

Lo script Windows e la variante NVIDIA sono predisposti; non sono stati eseguiti su hardware Windows/NVIDIA durante questo collaudo.
