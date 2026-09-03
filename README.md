# Camera Sensor Service

A containerized Python and OpenCV service for camera sensor stream acquisition, processing, and telemetry logging.

---

## Project Structure

```
.
├── .dockerignore         # Docker context exclusions
├── .gitignore            # Git ignore patterns for Python & media outputs
├── Dockerfile            # Python 3.11 slim + OpenCV runtime environment
├── docker-compose.yml    # Container orchestration & live volume mounts
├── requirements.txt      # Python dependencies (opencv, numpy, python-dotenv)
├── README.md             # Project documentation
└── src/
    └── main.py           # Camera stream ingestion & frame loop
```

---

## 1. Quick Start with Docker

### Build and Run with Docker Compose
```bash
docker compose up --build
```

### Run in Background (Detached)
```bash
docker compose up -d
```

### View Logs
```bash
docker compose logs -f camera-sensor
```

### Stop Service
```bash
docker compose down
```

---

## 2. Configuration Options

Set these in `docker-compose.yml` or via `.env`:

| Variable | Default | Description |
|---|---|---|
| `CAMERA_SOURCE` | `0` | Device index (`0`, `1`), RTSP URL (`rtsp://...`), or `mock` |
| `FRAME_WIDTH` | `640` | Video frame width in pixels |
| `FRAME_HEIGHT` | `480` | Video frame height in pixels |
| `FPS` | `30` | Target frame rate |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## 3. Local Development (Without Docker)

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
2. Activate environment:
   - **Windows:** `.venv\Scripts\activate`
   - **Linux/macOS:** `source .venv/bin/activate`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python src/main.py
   ```

---

## 4. Linking to Remote Git Repository

To link this local Git repository to GitHub, GitLab, or Bitbucket:

1. Create a new repository on your remote host (e.g., GitHub).
2. Link the remote origin:
   ```bash
   git remote add origin <REMOTE_REPOSITORY_URL>
   ```
3. Push your code to the default branch (`main`):
   ```bash
   git branch -M main
   git push -u origin main
   ```
