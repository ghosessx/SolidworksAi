# Contributing to SolidAI

Thank you for your interest in contributing to **SolidAI**! This guide outlines the project's coding standards, architecture rules, and testing procedures.

---

## 🛠️ Development Setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/YourUsername/SolidAI.git
   cd SolidAI
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 📐 Architecture & Coding Standards

SolidAI enforces strict separation of concerns across its 3 layers:

1. **CAD Engine Parity Rule**:
   - Every method added to `SolidWorksCADEngine` in `cad_engine.py` **must** have an identical method signature and return type (`StepResult`) in `MockCADEngine` (`mock_engine.py`).
   - Units in engine methods: lengths must be in **millimeters ($mm$)**, angles in **degrees ($^\circ$)**.

2. **Pydantic Schema Rule**:
   - Any new CAD operation must be registered in `cad_schema.py` under `CADStep` with appropriate type constraints and validation logic.
   - Maintain bilingual alias mapping (`part_name` / `parca_adi`, `action` / `islem`).

3. **Prompt & Few-Shot Alignment**:
   - When adding new operations, update `agent_prompt.py` and `vision_analyzer.py` system prompts so LLMs understand the valid syntax and parameters.

---

## 🧪 Testing & Verification

Before submitting a Pull Request, you must verify that all automated checks pass:

### 1. Codebase Consistency Audit
Verifies that all schemas, engine signatures, and prompt operations match 100%:
```bash
python tools/audit_codebase.py
```
*Expected: 0 signature mismatches, 0 schema mismatches.*

### 2. Headless Benchmark Suite
Runs the full 9-case evaluation suite against `MockCADEngine`:
```bash
python eval/run_benchmark.py
```
*Expected: 100% PASS on all functional and failure-injection tests.*

---

## 🚀 Submitting a Pull Request

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Commit your changes with clear, descriptive commit messages:
   ```bash
   git commit -m "feat(engine): add loft_boss parametric operation"
   ```
3. Push to your fork and submit a Pull Request targeting `main`.
4. Ensure all CI benchmark checks pass in your PR.
