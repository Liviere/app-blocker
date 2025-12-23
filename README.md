# 🚫 App Blocker

**App Blocker** is an application for monitoring and limiting time spent on specific programs on your computer. It allows you to set daily time limits for applications and automatically closes them when the limit is exceeded.

## 📋 Features

- ⏰ **Time Limits** - set daily limits for applications (in minutes)
- 🎯 **Automatic Closing** - applications are closed when limit is exceeded
- 📊 **Real-time Monitoring** - track current usage time
- 🖥️ **Graphical Interface** - easy management through GUI
- 📈 **Usage History** - data is saved day by day
- ⚙️ **Configurable Interval** - set how often the app checks processes
- 🚀 **Windows Autostart** - automatically start with Windows system boot
- 📱 **System Tray Integration** - minimize to system tray for background operation
- 💾 **State Persistence** - remembers monitoring state between sessions
- 🛡️ **Watchdog & Heartbeat** - detects forced terminations of the monitor, logs incidents, and can automatically restart it

## 🚀 Requirements

- **Python 3.9+**
- **Windows** (app uses `taskkill` to close processes and Windows registry for autostart)
- **Poetry** (for dependency management)

### Dependencies

- `psutil` - for process monitoring
- `pystray` - for system tray functionality
- `pillow` - for tray icon image processing
- `tkinter` - graphical interface (built into Python)

## 📦 Installation

### Using Poetry (Recommended)

1. **Install Poetry** (if you haven't already):

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

   Or on Windows:

   ```powershell
   (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
   ```

2. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd app-blocker
   ```

3. **Install dependencies**:

   ```bash
   poetry install
   ```

4. **Run the application**:

   ```bash
   # GUI version
   poetry run python gui.py

   # Command line monitoring
   poetry run python main.py
   ```

### Alternative Installation

If you prefer not to use Poetry, you can install dependencies manually:

```bash
pip install psutil pystray pillow
python gui.py  # For GUI
python main.py # For monitoring
```

## 🎯 Usage

### Basic Setup

1. **Start the GUI**: `poetry run python gui.py`
2. **Add applications** you want to monitor by clicking "Add App"
3. **Set time limits** for each application (in minutes)
4. **Start monitoring** by clicking "Start Monitoring"

### Advanced Features

#### Windows Autostart

- Check **"Start with Windows (autostart)"** to automatically launch App Blocker when Windows starts
- If system tray is enabled, the app will start minimized to tray on system boot

#### System Tray Integration

- Check **"Minimize to system tray"** to enable tray functionality
- Close button will minimize to tray instead of quitting the application
- Right-click tray icon for quick access to start/stop monitoring and show window
- Tray icon color changes: blue (stopped), green (monitoring active)

#### State Persistence

- App automatically remembers if monitoring was active when closed
- On next startup, monitoring will resume automatically if it was previously enabled
- Only works if applications are configured for monitoring

The application will:

- Track time spent in monitored applications
- Automatically close applications when daily limits are exceeded
- Save usage history for each day
- Remember monitoring state between sessions
- Run in background via system tray (if enabled)

## 🔧 Configuration

Configuration is stored in `config.json`:

- `apps`: Dictionary of applications and their daily limits (in minutes)
- `check_interval`: How often to check processes (in seconds)
- `enabled`: Whether monitoring is active (automatically managed)
- `autostart`: Enable automatic startup with Windows
- `minimize_to_tray`: Enable system tray functionality
- `watchdog_enabled`: Włącza strażnika sprawdzającego, czy monitor żyje
- `watchdog_restart`: Pozwala strażnikowi automatycznie restartować monitor
- `watchdog_check_interval`: Co ile sekund GUI sprawdza stan monitora
- `heartbeat_ttl_seconds`: Maksymalny wiek heartbeat zanim zostanie uznany za nieświeży
- `event_log_enabled`: Włącza logowanie zdarzeń do Windows Event Log (gdy dostępne)

### Logging and sabotage detection

- Log file: `app_blocker.log` in the application directory (start/stop events, limit breaches, watchdog).
- Heartbeat: `monitor_heartbeat.json` updated by the monitor process on each cycle.
- The GUI watchdog checks the monitor process and heartbeat freshness every few seconds:
   - if the process has died or the heartbeat is stale → an entry in the log (and Event Log if enabled), optional monitor restart.
   - Crash/force stop → `ERROR` in the Event Log + file; attempts to circumvent → `WARNING/ERROR` in the Event Log + file.

## 🧪 Testing

The project includes comprehensive tests that use isolated configuration files to avoid interfering with your actual App Blocker settings.

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run tests with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_with_utils.py

# Run tests and generate coverage report
poetry run pytest --cov=. --cov-report=html
```

### Test Structure

- `tests/test_app_blocker.py` - Basic functionality tests
- `tests/test_autostart.py` - Windows autostart functionality tests
- `tests/test_system_tray.py` - System tray integration tests
- `tests/test_isolated_config.py` - Advanced tests with isolated configuration
- `tests/test_with_utils.py` - Example tests using test utilities
- `tests/test_utils.py` - Utilities for creating isolated test environments

### Test Isolation

All tests use temporary directories and mock configurations to ensure:

- Your actual `config.json` and `usage_log.json` files are never modified
- Tests run in complete isolation from your real App Blocker settings
- Multiple test runs don't interfere with each other

## 🛠️ Development

### Setting up Development Environment

```bash
# Install development dependencies
poetry install

# Format code with Black
poetry run black .

# Lint code with Flake8
poetry run flake8 .

# Run tests
poetry run pytest
```
### Versioning

- The current application version is stored exclusively in `pyproject.toml`.
- The `versioning.py` module exposes a `get_version()` function and a `VERSION` constant used by tests and scripts (e.g., the installer).
- When updating the version, edit only `pyproject.toml`; the rest of the tools will read it automatically.

## 📦 Building Distribution

### Prerequisites

1. **Install Inno Setup** (for Windows installer):

   - Download from: https://jrsoftware.org/isinfo.php
   - Install with default settings

2. **Install development dependencies**:
   ```bash
   poetry install
   ```

### Build Process

Using the provided batch script:

```bash
# Run complete build process (clean, test, build, installer)
make.bat all

# Or individual steps:
make.bat clean     # Clean previous builds
make.bat test      # Run tests
make.bat build     # Build executables only
make.bat installer # Create installer only
```

### Distribution Contents

After building, you'll find:

- **`dist/app-blocker/`** - Portable application folder

  - `app-blocker.exe` - Command-line monitor
  - `app-blocker-gui.exe` - GUI application
  - `config.default.json` - Default configuration
  - `App Blocker GUI.bat` - GUI launcher
  - `App Blocker Monitor.bat` - Monitor launcher
  - `README.md` - Documentation

- **`dist/installer/app-blocker-setup-{version}.exe`** - Windows installer

### Windows Installer Features

- ✅ **Easy Installation**: One-click setup
- ✅ **Desktop Shortcuts**: Optional desktop icons
- ✅ **Start Menu Integration**: App appears in start menu
- ✅ **Automatic Config**: Creates default configuration from template
- ✅ **Multi-language**: Supports English and Polish
- ✅ **Clean Uninstall**: Removes all components including user configs
- ✅ **Auto-launch**: Option to start app after installation

### Testing Distribution

```bash
# Test built executables
poetry run python test_distribution.py
```

This will verify:

- All required files are present
- Executables run correctly
- Batch files work properly

## 📋 Configuration Examples

### Command Line Usage

```bash
# Start GUI normally
poetry run python gui.py

# Start GUI minimized to tray (if tray is enabled in config)
poetry run python gui.py --minimized

# Start monitoring only (background process)
poetry run python main.py
```

## 🔧 Troubleshooting

### System Tray Issues

- If tray icon doesn't appear, ensure `pystray` and `pillow` are installed
- On some systems, tray icons may be hidden in the system tray overflow area
- Restart the application if tray functionality stops working

### Autostart Issues

- Autostart uses Windows Registry (`HKEY_CURRENT_USER\SOFTWARE\Microsoft\Windows\CurrentVersion\Run`)
- If autostart doesn't work, check Windows Task Manager > Startup tab
- Administrator privileges are not required for current user autostart

### Monitoring Issues

- If monitoring doesn't start automatically, check that applications are configured
- Ensure the monitoring process has permission to terminate target applications
- Check the console output for error messages
