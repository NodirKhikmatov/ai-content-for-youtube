# Contributing to ai-content-for-youtube ("The Turning Point")

Thank you for your interest in contributing to **The Turning Point**! We welcome contributions from developers, researchers, and creators.

---

## 🚀 Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/<your-username>/ai-content-for-youtube.git
   cd ai-content-for-youtube
   ```
3. **Set up the development environment**:
   ```bash
   cd studio
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
4. **Copy the example environment file**:
   ```bash
   cp .env.example .env
   # Populate required API keys (or use fake backends for zero-cost testing)
   ```
5. **Start PostgreSQL database**:
   ```bash
   docker compose up -d
   ```

---

## 🧪 Testing and Quality Checks

Before submitting a Pull Request, ensure that all tests and linting checks pass:

```bash
cd studio

# Run unit and integration tests
pytest

# Check code formatting and linting
ruff check .
ruff format --check .

# Run static type checking
mypy src
```

---

## 🏗 Submitting a Pull Request (PR)

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Write clean, documented code and include appropriate unit tests.
3. Commit your changes with clear, descriptive commit messages:
   ```bash
   git commit -m "feat(agent): add support for custom voice cloning in VoiceSynthesis"
   ```
4. Push to your branch and open a Pull Request against `main`.
5. Clearly describe the changes, rationale, and any manual verification steps in your PR description.

---

## 📜 Code of Conduct

Please review and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md) in all project interactions.
