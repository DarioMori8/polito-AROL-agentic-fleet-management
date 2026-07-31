# AROL Multi-Agent Conversational Ecosystem — Frontend Client

Mobile-first Progressive Web Application (PWA) tailored for on-field maintenance technicians and industrial plant operators. Built on AROL's **Rugged UI** design language, it is optimized for high-contrast visibility and gloved touch interactions on rugged devices (smartphones, tablets, and industrial PMAs).

This frontend acts as the user-facing interface for the AROL conversational ecosystem, allowing users to scan machine QR codes, consult an AI-driven multi-agent troubleshooter, stream live LLM diagnostic insights, and view grounded vector DB manual segments alongside interactive CAD blueprints.

---

## 🛠️ Tech Stack & Key Configurations

| Layer | Technology | Operational Notes |
| :--- | :--- | :--- |
| **Framework** | React 19 + Vite 8 | Single Page Application (SPA) optimized for low footprint. |
| **Routing** | React Router DOM v6 | Decoupled landing, fleet tracking, and diagnostic paths. |
| **Icons** | Lucide React | High-contrast, standardized industrial iconography. |
| **PWA Layer** | `vite-plugin-pwa` | Manages standalone manifest, assets precaching, and workers. |
| **Styling** | Vanilla CSS3 | Rigorous, framework-less design tokens for speed and consistency. |
| **Production Server** | Nginx 1.25 (Alpine) | Serving static optimized assets with SPA routing fallbacks. |

### Path Aliasing & Expositions
*   **Path Alias**: `@` mapped to `src/` (e.g., `import ManualViewer from '@/components/manuals/ManualViewer'`).
*   **Dev Server**: Port `3000`, exposed across local networks (`--host`) to allow on-site testing with physical rugged devices via QR codes.

---

## 📐 Industrial Design System (Rugged UI)

Specially designed for hazardous, low-light, or high-glare bottling plant environments. All interactive touch targets are strictly designed to be **$\ge$ 48px** in height and width to support gloved operations (WCAG 2.1 compliance).

### Style Tokens (`App.css` / `Stile del css da seguire`)
*   `--arol-blue`: `#002D54` — Primary operations, structural frames, and main buttons.
*   `--arol-sky`: `#407B9E` — Interactive elements, selectors, links, and minor active states.
*   `--arol-red`: `#C0392B` — Active alarms, threshold exceptions, and critical device failures.
*   `--arol-green`: `#27AE60` — Normal operations, synchronized status, and healthy telemetry.
*   `--arol-dark`: `#1A252F` — Heavy text contrasting on light sheets.
*   `--arol-bg`: `#F8FAFC` — Overall canvas background.

---

## 🚀 Implemented Architectural Features (Fase 1 - 3)

The frontend contains a full-fledged production-ready vertical slice matching the requirements of the **AROL Conversational Ecosystem**:

### 1. Dynamic Asset Management (`MachineContext.jsx`)
*   **Backend Integration**: Dynamically queries the list of AROL fleet machines (`GET /v1/machines`) and resolved assets (`GET /v1/machines/{id}`).
*   **Multi-Tier Offline Caching**: Persists fleet records and selected machine metadata in `sessionStorage` (`arol_cached_fleet`, `arol_active_machine`). If the technician enters a Wi-Fi blind spot in the facility, the interface triggers a **graceful fallback**, rendering the cached profiles and showing an offline banner rather than locking the UI.

### 2. Custom SSE Stream Parser (`useChatStream.js`)
*   **POST-Based EventStream reader**: Since native browser `EventSource` restricts requests to `GET`, this hook consumes a custom chunk-by-chunk stream reader using standard `fetch` API and JavaScript `ReadableStream`.
*   **Real-Time Token Rendering**: Consumes the `POST /v1/chat/stream` endpoint, parsing SSE events (`token`, `citations`, `session`, `error`) on the fly. Words are appended to the chat bubble in real-time.
*   **Conversational Memory Persistence**: Automatically captures the LangGraph thread's `session_id` and saves it locally. Subsequent queries reuse the active session identifier so the agents retain multi-turn context (e.g., remembering previous errors and parts discussed).
*   **Network Resiliency**: Includes an `AbortController` reference. Navigating away, switching tabs, or selecting a new machine cancels the active request on the spot, preventing thread leaks and processing load on the server.

### 3. Smart Document CAD Blueprint Viewer (`ManualViewer-v2.jsx`)
*   **Dynamic Document Syncing**: Queries `GET /v1/machines/{id}/manuals` to list the actual technical documents available on the server.
*   **AI Citation Routing**: Integrates with the Chat Feed. Clicking on a citation card (e.g., `[Manuale_Euro_VP_Manutenzione.pdf, Page 24]`) triggers dynamic page-shifting. The viewer updates document selectors, flips to the target page, and anchors the viewport.
*   **Vector DB Segment Injection**: Receives the original document chunk retrieved from Chroma DB (`selectedCitation.snippet`) and injects it into a high-visibility, high-contrast banner overlaying the CAD drawing.
*   **Offline Fallback Database**: Embeds an offline fallback copy (`FALLBACK_MANUALS_DATABASE`) with pre-programmed SVG/CSS blueprints for Euro VP capping heads, baseplates, cam assemblies, and anchor bolts to enable offline exam simulations.
*   **Advanced View Control**: Tactile zoom controls (70% to 150%), viewport-scroll synchronization, fullscreen mode (Natively using Fullscreen API), and an internal keyword index search.

### 4. Interactive Conversational Interface (`App-v3.jsx`)
*   **State-Filtered Fleet View**: Searchable list supporting status filtering (All, Operational, In Alarm).
*   **GPU In-Progress Waiting State**: Disables chat inputs and shows animated loading indicators while the backend GPU-orchestrator processes heavy agent pipelines.

---

## 📂 Project Structure (`/frontend`)

```text
frontend/
├── dist/                          # Optimized static files generated during production builds
├── public/
│   ├── manifest.json              # Progressive Web App standalone configuration
│   └── favicon.ico
├── src/
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatWindow.jsx     # Controls chat feed and prompt suggestions
│   │   │   └── ChatBubble.jsx     # Individual balloon rendering markdown, alerts, and citations
│   │   └── manuals/
│   │       └── ManualViewer.jsx   # Vector CAD reader, zoom engine, and RAG chunk injector
│   ├── context/
│   │   └── MachineContext.jsx     # Context provider for Fleet Sync and Offline Caching
│   ├── hooks/
│   │   └── useChatStream.js       # Core SSE fetch stream parser and session memory engine
│   ├── pages/
│   │   ├── LandingQR.jsx          # Redirecting target post-QR scan with ID resolution
│   │   └── ChatWorkspace.jsx      # Mobile Tab / Tablet Split-Screen Layout orchestrator
│   ├── App.jsx                    # Routing table and global stream coordinator (v3)
│   ├── App.css                    # UI color tokens and overall industrial reset rules
│   └── main.jsx
├── Dockerfile                     # Multi-stage optimized Docker deployment model
├── nginx.conf                     # Nginx client-side redirection configuration (Anti-404 SPA)
├── package.json                   # Client-side node library manifests
└── vite.config.js                 # Dev-server routing, LAN exposing, and path alias rules
```

---

## 🚀 Getting Started & Running Instructions

Ensure you have **Node.js (v20+ recommended)** installed on your machine.

### Method A: Local Development Run (Senza Docker)

#### 1. Install Dependencies
Navigate into the `/frontend` workspace and install the package manifests:
```bash
npm install
```

#### 2. Configure Environment Variables
Create a local `.env` file in the root of the `/frontend` directory to point to your backend orchestrator endpoint:
```bash
# Create local configuration
echo "VITE_API_URL=http://localhost:8000" > .env
```
*(Use the `.env.example` file as a reference for multi-stage deployments).*

#### 3. Start the Development Server
Launch the development environment exposed to your local area network (LAN) for testing on physical devices:
```bash
npm run dev
```
*   **Local URL**: `http://localhost:3000`
*   **Network URL (LAN)**: `http://192.168.x.x:3000` *(Scan the console-generated QR code with your mobile device to test live interactions directly on the factory floor).*

---

### Method B: Production Build & Run (Con Docker)

To compile the application in optimized standalone production mode and serve it with a high-performance Nginx server:

#### 1. Build the Docker Image
Execute the build context pointing to our multi-stage docker configurations:
```bash
docker build -t arol-frontend .
```

#### 2. Run the Container
Launch the container mapping Nginx's exposed port `3000` to your host computer:
```bash
docker run -d -p 3000:3000 --name arol-frontend-client arol-frontend
```

#### 3. Multi-Service Run (Docker Compose)
If launching within the global monorepo using Docker Compose, append the following node to your root `docker-compose.yml` file:
```yaml
version: '3.8'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - backend
```
Boot all ecosystem containers dynamically using:
```bash
docker-compose up --build -d
```

---

## 🛡️ Nginx Routing Explanation (Production Build Safety)

In production, since React utilizes client-side routing (`react-router-dom`), reload attempts or deep URL requests (e.g., bookmarking `/workspace/001` or entering it manually in the browser bar) would trigger standard Nginx directory lookups, culminating in a **`404 Not Found`** crash.

To protect operators against accidental session reloads, the production container embeds an optimized `nginx.conf` utilizing:
```nginx
location / {
    root /usr/share/nginx/html;
    index index.html index.htm;
    try_files $uri $uri/ /index.html;
}
```
This forces Nginx to intercept any deep requests, resolve them, and delegate the UI rendering back to our `index.html` file, where the React routing tree can cleanly resume the session.
