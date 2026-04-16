# Architecture Overview

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Web Browser / Client                      │
│                  (Modern React/Vue Ready)                     │
└────────────────────────────┬─────────────────────────────────┘
                             │ REST API + WebSocket
                             ↓
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI Backend Server                      │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ HTTP Routers                                           │  │
│  │ • /api/devices  - Device management                   │  │
│  │ • /api/tests    - Test execution & results            │  │
│  │ • /api/health   - System health & status              │  │
│  └────────────────────────────────────────────────────────┘  │
│                             │                                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Services (Business Logic)                              │  │
│  │ • DeviceManager    - Device registry & operations     │  │
│  │ • TestOrchestrator - Test execution & scheduling      │  │
│  │ • MQTTManager      - Message broker communication     │  │
│  │ • ConfigManager    - Config file management            │  │
│  └────────────────────────────────────────────────────────┘  │
│                             │                                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Test Executors (Pluggable)                             │  │
│  │ • BaseExecutor          - Abstract base               │  │
│  │ • ConnectivityExecutor  - Network tests               │  │
│  │ • SpeedTestExecutor     - Performance tests           │  │
│  │ • PortForwardExecutor   - Forwarding tests            │  │
│  │ • Custom Executors      - User-defined tests          │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                             │ MQTT Pub/Sub
                             ↓
┌──────────────────────────────────────────────────────────────┐
│               MQTT Message Broker (Mosquitto)                 │
│                                                             │
│  Topics:                                                     │
│  • device_data       ← Devices publish status              │
│  • server_info       ← Server broadcasts messages          │
│  • test_commands     → Server sends test commands          │
│  • test_results      ← Clients publish results             │
└──────────────────────────────────────────────────────────────┘
                             │ MQTT Subscribe
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
   ┌─────────┐          ┌─────────┐          ┌─────────┐
   │ Device  │          │ Device  │          │ Device  │
   │  Client │          │  Client │          │  Client │
   │ (RATS)  │          │ (RATS)  │          │ (RATS)  │
   └─────────┘          └─────────┘          └─────────┘
```

## Component Details

### 1. Frontend (Web UI)
**Technology:** HTML5, CSS3, Vanilla JavaScript
**Responsibilities:**
- Device selection and listing
- Test group and case selection
- Test execution triggering
- Real-time result display
- Report viewing

**Key Files:**
- `index.html` - Main UI structure
- `api.js` - API client/HTTPS communication
- `ui.js` - DOM manipulation and UI logic
- `app.js` - Main application orchestration
- `styles.css` - Styling

### 2. FastAPI Backend (Core Server)
**Technology:** Python, FastAPI, Pydantic, Asyncio
**Responsibilities:**
- REST API endpoints
- Request validation
- Business logic orchestration
- MQTT integration
- Configuration management
- Logging and monitoring

**Key Modules:**
- `main.py` - FastAPI application setup
- `settings.py` - Configuration from environment
- `api/` - REST endpoint routers
- `services/` - Business logic services
- `test_executors/` - Test implementation plugins
- `schemas/` - Pydantic data models

### 3. Services Layer
**Business Logic Abstractions**

#### DeviceManager
- Maintains device registry (in-memory + persistent JSON)
- Device discovery and status tracking
- Device info updates
- Serialization to/from config files

#### TestOrchestrator
- Test definition management
- Execution tracking
- Result recording
- Execution summary calculation
- Config file management

#### MQTTManager
- Connection management to MQTT broker
- Publish/Subscribe operations
- Topic subscription with callbacks
- Async message handling
- Reconnection logic

#### ConfigManager
- JSON config file operations
- Device configuration persistence
- Test configuration persistence
- Repository URL management

### 4. Test Executors (Pluggable Architecture)
**Technology:** Python Async Classes
**Base Class:** `BaseTestExecutor`

Each executor:
1. Inherits from BaseTestExecutor
2. Implements `execute()` async method
3. Returns: (passed: bool, output: str, errors: List[str])
4. Registered in executor registry
5. Instantiated dynamically on demand

**Lifecycle:** setup() → execute() → teardown()

**Current Implementations:**
- `ConnectivityTestExecutor` - Network connectivity tests
- `SpeedTestExecutor` - Speed/bandwidth tests
- `PortForwardTestExecutor` - Port forwarding tests

### 5. MQTT Communication
**Topics Structure:**
```
device_data/         ← Device publishes device info
├── device_id
├── status
└── timestamp

test_commands/       → Server sends test commands
├── command_id
├── test_id
└── parameters

test_results/        ← Client publishes test results
├── execution_id
├── test_id
├── passed (bool)
└── timestamp

server_info/         ← Server broadcasts info
├── version
├── status
└── timestamp
```

**Quality of Service (QoS):** 1 (At least once delivery)

## Data Flow

### Device Registration Flow
```
Device → MQTT (device_data) 
      → Backend (receives via MQTT subscription)
      → DeviceManager (stores/updates)
      → JSON config (persisted)
      → Frontend (fetched via API)
```

### Test Execution Flow
```
Frontend (HTTP POST /api/tests/execute)
      → Backend (receives request)
      → TestOrchestrator (creates execution record)
      → Background task spawned
      → For each test:
         → Get test executor
         → Run execute()
         → Record result
         → Publish via MQTT
      → Frontend polls /api/tests/execution/{id}
      → Results displayed in real-time
```

## Configuration Management

### Configuration Files
Located in `./config/` directory:

1. **devices.json** - Device registry
```json
{
  "devices": [
    {"id": "...", "name": "...", "mac_address": "..."}
  ]
}
```

2. **tests.json** - Test definitions
```json
{
  "test_groups": {
    "groupname": [{"id": "...", "name": "..."}]
  }
}
```

3. **repo.txt** - Repository URL
4. **.env** - Environment variables

### Environment Variables
```
MQTT_BROKER, MQTT_PORT
DEBUG, LOG_LEVEL
HOST, PORT
CONFIG_DIR, LOG_DIR, REPORT_DIR
```

## Scalability Considerations

### Horizontal Scaling
- Stateless backend design (no session state)
- Multiple backend instances can share same MQTT broker
- Config files can be stored in shared volume
- Load balancer in front of backends

### Vertical Scaling
- Async/await enables high concurrency
- Worker pool for CPU-bound tests
- Connection pooling for MQTT
- Efficient JSON serialization

### Performance Optimizations
- MongoDB for large datasets (optional future)
- Redis caching (optional future)
- Test result compression
- Pagination for device/test listing

## Security Architecture

### Current Implementation
- No authentication required (development mode)
- Config files world-readable
- MQTT no authentication

### Production Recommendations
- Enable MQTT authentication
- JWT tokens for API endpoints
- TLS/SSL for all connections
- API key management
- Rate limiting
- Input validation (Pydantic does this)
- CORS configuration
- Secrets management (environment variables)

## Extension Points

### Adding New Tests
1. Extend `BaseTestExecutor`
2. Implement `execute()` method
3. Register in `EXECUTOR_REGISTRY`
4. Add to test config JSON

### Custom Services
1. Create service class
2. Implement business logic
3. Use dependency injection
4. Update main.py

### API Endpoints
1. Create router module in `api/`
2. Use dependency injection for services
3. Return Pydantic models
4. Include in main.py

## Deployment Architecture

### Docker Compose
- Frontend service (Nginx)
- Backend service (FastAPI)
- MQTT service (Mosquitto)
- Shared volumes for config/logs

### Kubernetes
- Pod per service
- ConfigMaps for configuration
- Persistent volumes for data
- Services for discovery
- Ingress for external access

### Single Node
- All services in one docker-compose stack
- SQLite for persistence (optionally)
- File-based config

---

**Version:** 2.0.0
**Last Updated:** 2024-01-16
