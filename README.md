# 🚫 App Blocker

**App Blocker** is an application for monitoring and limiting time spent on specific programs on your computer. It allows you to set daily time limits for applications and automatically closes them when the limit is exceeded.

## 📋 Features

- ⏰ **Time Limits** - set daily limits for applications (in minutes)
- 🎯 **Automatic Closing** - applications are closed when limit is exceeded
- 📊 **Real-time Monitoring** - track current usage time
- 🖥️ **Graphical Interface** - easy management through GUI
- 📈 **Usage History** - data is saved day by day
- ⚙️ **Configurable Interval** - set how often the app checks processes

## 🚀 Requirements

- **Python 3.8.1+**
- **Windows** (app uses `taskkill` to close processes)
- **Poetry** (for dependency management)

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
pip install psutil
python gui.py  # For GUI
python main.py # For monitoring
```

## 🎯 Usage

1. **Start the GUI**: `poetry run python gui.py`
2. **Add applications** you want to monitor by clicking "Add App"
3. **Set time limits** for each application (in minutes)
4. **Enable monitoring** by checking the "Enable Monitoring" checkbox
5. **Start monitoring** by clicking "Start Monitoring"

The application will:

- Track time spent in monitored applications
- Automatically close applications when daily limits are exceeded
- Save usage history for each day

## 🔧 Configuration

Configuration is stored in `config.json`:

- `apps`: Dictionary of applications and their daily limits (in minutes)
- `check_interval`: How often to check processes (in seconds)
- `enabled`: Whether monitoring is active

## 📊 Dependencies

- `psutil` - for process monitoring
- `tkinter` - graphical interface (built into Python)

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
