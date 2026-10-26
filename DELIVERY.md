# AROL Fleet Management — guida per la consegna

## Avvio rapido per il docente

1. **Installare e aprire [Docker Desktop](https://www.docker.com/products/docker-desktop/)**. Su Linux va bene anche Docker Engine con Docker Compose v2. Attendere che Docker risulti avviato.
   Verificare di aver assegnato a Docker **almeno 16 GB di RAM**. Nelle installazioni che mostrano il limite in Docker Desktop: **Settings → Resources → Advanced → Memory**, quindi applicare e riavviare. Con WSL2 la memoria della macchina virtuale si configura nelle impostazioni WSL. La RAM totale del computer e quella assegnata a Docker sono due valori diversi.
2. **Estrarre tutto il pacchetto ZIP** in una cartella locale. I PDF devono essere già presenti in `data/manuals/`.
3. **Avviare il progetto**:
   - **Windows:** doppio clic su `avvia.bat` nella cartella estratta.
   - **macOS/Linux:** aprire il terminale nella cartella estratta ed eseguire `sh avvia.sh`.
   - **Con GPU NVIDIA su Windows/Linux:** dopo i [prerequisiti GPU](#gpu-nvidia-opzionale), usare invece `avvia-gpu.bat` su Windows oppure `sh avvia-gpu.sh` su Linux.
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
4. Avvio di Langfuse e dei suoi servizi; creazione automatica di organizzazione, progetto, account e chiavi API.
5. Verifica della presenza dei manuali di tutte le otto macchine.
6. Download di **`llama3.1:8b`**, usato dall'orchestratore e dagli agenti, e **`nomic-embed-text`**, usato per gli embedding. I modelli già presenti vengono riutilizzati.
7. Prova reale di generazione di un token, con la stessa finestra di contesto della chat, prima di iniziare l'ingestion. In modalità NVIDIA viene controllata anche la memoria GPU effettivamente usata dal modello: se è zero il setup si ferma. In modalità CPU il modello viene subito scaricato dalla RAM; in modalità GPU resta disponibile fino a cinque minuti di inattività o fino al caricamento del modello di embedding. I pesi restano nel volume.
8. Estrazione del testo dei PDF, suddivisione in frammenti e costruzione dell'indice Chroma.
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

Se si usa NVIDIA, riavviare sempre con **`avvia-gpu.bat`** oppure **`sh avvia-gpu.sh`**, anche dopo un aggiornamento dei sorgenti. Gli script normali selezionano la CPU; modelli, indice e dati sono gli stessi in entrambe le modalità. I comandi di avvio Compose a un solo file riportati qui sotto selezionano anch'essi la CPU; per mantenere NVIDIA aggiungere `-f compose.delivery.gpu.yml` subito dopo `-f compose.delivery.yml`.

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

**Llama 3.1 8B può usare una GPU NVIDIA attraverso Ollama.** Il pacchetto mantiene la stessa immagine Ollama e gli stessi modelli; `compose.delivery.gpu.yml` assegna le GPU al solo servizio Ollama. L'immagine fissata alla versione 0.13.5 include già le librerie CUDA: non occorre installare Python, PyTorch o il CUDA Toolkit dentro gli altri container. [Dockerfile ufficiale della versione inclusa](https://github.com/ollama/ollama/blob/v0.13.5/Dockerfile).

### Preparazione del computer (una sola volta)

- **Windows 10/11 con NVIDIA:** installare driver NVIDIA aggiornati, aggiornare WSL con `wsl --update` e abilitare **Use the WSL 2 based engine** in Docker Desktop. Usare i container Linux. Il backend Hyper-V non fornisce questo passaggio della GPU ai container. [Prerequisiti ufficiali Docker per Windows](https://docs.docker.com/desktop/features/gpu/).
- **Linux con NVIDIA:** usare Docker Engine sul sistema con GPU, installare i driver e il **NVIDIA Container Toolkit** seguendo la [guida ufficiale NVIDIA](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). Configurare il runtime e riavviare Docker con i comandi seguenti. La guida NVIDIA riporta anche la configurazione specifica per Docker rootless.

```sh
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Il riavvio di Docker interessa anche gli altri container eventualmente attivi sul computer. Driver e runtime sono prerequisiti del sistema ospitante e vanno configurati una volta da chi amministra il PC. [Procedura Ollama per NVIDIA in Docker](https://docs.ollama.com/docker).

Questa modalità è destinata a PC/server con NVIDIA compatibile con Ollama e driver aggiornati. Non abilita Metal sui Mac né le GPU AMD. Sistemi Jetson/JetPack richiedono configurazione specifica e non sono coperti dal launcher standard.

Come stima per Llama 8B quantizzato con contesto di 8.192 token, prevedere **8 GB di VRAM libera come punto di partenza**, preferibilmente **12 GB per avere margine**. Non è un minimo certificato: la memoria necessaria dipende da GPU, contesto e modello. La VRAM è distinta dalla RAM di sistema; restano le risorse richieste dagli altri servizi. Con poca VRAM Ollama può distribuire il modello tra GPU e CPU, riducendo il beneficio in velocità.

### Avvio semplice e controlli automatici

- **Windows:** doppio clic su **`avvia-gpu.bat`**.
- **Linux:** eseguire **`sh avvia-gpu.sh`** nella cartella estratta.

Gli stessi avvii sono disponibili come `avvia.bat --gpu` e `sh avvia.sh --gpu`. Usare sempre il launcher GPU per i successivi riavvii; per tornare alla CPU usare quello normale.

Il launcher esegue prima `nvidia-smi -L` in un container temporaneo ricavato dalla stessa immagine Ollama, con la stessa richiesta di GPU. Se Docker non vede NVIDIA, termina **prima di fermare l'applicazione già in esecuzione**. Durante il setup, dopo una vera generazione di prova, controlla `size_vram` nell'[API dei modelli caricati di Ollama](https://docs.ollama.com/api/ps):

- **`GPU check passed`** indica che Llama ha allocato memoria GPU.
- **`partially on GPU`** segnala l'uso misto GPU/CPU: l'avvio è consentito, ma può essere più lento.
- **`no GPU memory`** blocca il setup; il pacchetto non dichiara pronta la modalità GPU se Llama sta usando solo la CPU.

L'uso della GPU viene verificato per Llama durante il setup. Il modello di embedding usa lo stesso server Ollama, che ne gestisce automaticamente l'esecuzione; non viene certificato separatamente il suo caricamento sulla GPU.

Per un controllo manuale dell'accesso NVIDIA, senza avviare l'app:

```sh
docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml run --rm --no-deps --entrypoint nvidia-smi ollama -L
```

Per avviare direttamente tramite Compose, da stack fermo:

```sh
docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml up --build --wait --wait-timeout 7200
```

Durante una domanda alla chat, o subito dopo, verificare dove risiede il modello:

```sh
docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml exec ollama ollama ps
docker compose -f compose.delivery.yml -f compose.delivery.gpu.yml logs --tail 100 setup ollama
```

La colonna `PROCESSOR` di `ollama ps` distingue GPU, CPU e caricamento misto. Se non mostra modelli, può essere già scaduto il periodo di permanenza in memoria: ripetere durante una richiesta. Il modello di embedding può sostituire temporaneamente Llama perché il pacchetto carica un modello alla volta.

Per ridurre la memoria richiesta, prima del launcher GPU si può impostare `DELIVERY_NUM_CTX=4096`: `export DELIVERY_NUM_CTX=4096` su Linux, `set DELIVERY_NUM_CTX=4096` nel Prompt dei comandi Windows oppure `$env:DELIVERY_NUM_CTX="4096"` in PowerShell. Un contesto più piccolo lascia meno spazio a cronologia e documenti; non garantisce prestazioni o qualità equivalenti.

L'accelerazione NVIDIA può migliorare i tempi di inferenza, ma non corregge gli errori di ragionamento, traduzione o scelta degli strumenti del modello. La configurazione segue la [specifica GPU di Docker Compose](https://docs.docker.com/compose/how-tos/gpu-support/); il collaudo su una GPU reale resta necessario per misurare memoria e tempi.

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
| `could not select device driver` o `nvidia-smi` fallisce | Verificare driver e NVIDIA Container Toolkit su Linux, oppure driver, WSL2 e backend Docker Desktop su Windows. Il launcher GPU non passa automaticamente alla CPU. |
| `no GPU memory` durante il setup | Leggere i log Ollama: controllare compatibilità della GPU, driver, runtime e VRAM libera. Rilanciare il launcher GPU dopo la correzione. |
| `partially on GPU` o uso misto in `ollama ps` | Liberare VRAM occupata da altre applicazioni o provare `DELIVERY_NUM_CTX=4096`; la parte del modello sulla CPU può rallentare le risposte. |
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

### Verifiche dell'avvio NVIDIA (26 ottobre 2026)

- Aggiunti `avvia-gpu.bat` e `avvia-gpu.sh`, con verifica NVIDIA prima di fermare l'app e controllo della VRAM di Llama prima dell'ingestion.
- Configurazioni Compose CPU e NVIDIA validate, comprese la richiesta di GPU, le variabili del setup e il riutilizzo degli stessi volumi.
- Immagine degli agenti ricostruita; **36 test mirati degli agenti** e **5 test dei launcher POSIX** superati. I casi GPU positivi sono simulati: includono caricamento interamente/parzialmente in VRAM, ripiego su CPU, modello assente e fallimento della verifica.
- Sul Mac senza NVIDIA il launcher GPU è stato realmente eseguito: ha rifiutato l'avvio e i container dell'app già attivi sono rimasti in esecuzione.
- Prova reale di un token su CPU completata con il nuovo bootstrap. Richiedendo poi la GPU allo stesso Ollama, il controllo ha correttamente rifiutato la VRAM pari a zero.

Non è stato possibile eseguire una generazione su GPU NVIDIA reale o avviare i file `.bat` su Windows. Non sono quindi certificati tempi di risposta, VRAM necessaria o funzionamento su uno specifico modello di scheda. Le prove del 25 ottobre restano il riferimento per il percorso completo della chat su CPU.
