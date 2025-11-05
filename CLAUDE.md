# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DocAgent is a multi-agent system for automated code documentation generation in Python codebases. It uses a hierarchical traversal approach combined with specialized AI agents to generate high-quality, context-aware docstrings.

**Key Architecture Concepts:**
1. **Hierarchical Traversal**: Uses dependency-first DFS traversal to process components with fewer dependencies first, building a documented foundation before tackling complex code
2. **Multi-Agent System**: Orchestrator coordinates specialized agents (Reader, Searcher, Writer, Verifier) in an iterative workflow
3. **Dual Interface**: Command-line interface for batch processing and web UI for interactive monitoring

## Essential Configuration

**Before running anything**, you must create `config/agent_config.yaml`:
```bash
cp config/example_config.yaml config/agent_config.yaml
# Edit agent_config.yaml to add your API keys
```

The config file specifies:
- LLM provider (Claude, OpenAI, Gemini, or HuggingFace)
- API keys and model selection
- Rate limits and cost tracking
- Flow control parameters (max search attempts, rejection cycles)
- Docstring options (overwrite behavior)

## Development Commands

### Installation
```bash
# Install core dependencies
pip install -e .

# Install with optional extras
pip install -e ".[dev]"           # Development tools (pytest, black, flake8)
pip install -e ".[visualization]" # Graph visualization (matplotlib, pygraphviz)
pip install -e ".[all]"           # Everything
```

### Running Tests
```bash
# Run all tests
export PATH="$HOME/.local/bin:$PATH"  # If pytest not in PATH
pytest

# Run tests with coverage
pytest --cov=src

# Run specific test file
pytest src/web_eval/test_docstring_parser.py
```

**Note**: Functions starting with `test_` are automatically discovered as test functions by pytest. Helper functions should use different prefixes like `run_`, `check_`, or `helper_`.

### Docstring Generation

**Basic Usage:**
```bash
# Generate docstrings for a repository
python generate_docstrings.py --repo-path <path>

# Test mode with placeholders (no LLM calls)
python generate_docstrings.py --repo-path <path> --test-mode placeholder

# Overwrite existing docstrings
python generate_docstrings.py --repo-path <path> --overwrite-docstrings

# Use different ordering modes
python generate_docstrings.py --repo-path <path> --order-mode topo        # Default: dependency-based
python generate_docstrings.py --repo-path <path> --order-mode random_node  # Random component order
python generate_docstrings.py --repo-path <path> --order-mode random_file  # Random file order
```

**Removing Docstrings (for testing):**
```bash
./tool/remove_docstrings.sh data/raw_test_repo
./tool/remove_docstrings.sh --dry-run data/raw_test_repo  # Preview changes
```

### Web Interfaces

**Generation Web UI:**
```bash
# Local
python run_web_ui.py

# Remote server
python run_web_ui.py --host 0.0.0.0 --port 5000
# Then tunnel: ssh -L 5000:localhost:5000 user@host
```

**Evaluation Web UI:**
```bash
# Local
python src/web_eval/app.py

# Remote server
python src/web_eval/app.py --host 0.0.0.0 --port 5001
# Then tunnel: ssh -L 5001:localhost:5001 user@host
```

### Local LLM Setup (Optional)
```bash
# Serve a local model
bash tool/serve_local_llm.sh

# Configure agent_config.yaml:
# - Set type: "huggingface"
# - Set api_base: "http://localhost:8000/v1"
# - Set model to your model name
```

## Code Architecture

### Core Components

**1. Multi-Agent System (`src/agent/`)**

The agent workflow is managed by an Orchestrator that coordinates:
- **Reader** (`reader.py`): Analyzes code and determines what additional context is needed
- **Searcher** (`searcher.py`): Retrieves information from internal codebase (AST traversal) or external sources (web search via Perplexity API)
- **Writer** (`writer.py`): Generates Google-style docstrings using accumulated context
- **Verifier** (`verifier.py`): Evaluates quality and requests revisions if needed
- **Orchestrator** (`orchestrator.py`): Manages the iterative loop with retry limits

All agents inherit from `BaseAgent` (`base.py`) which provides LLM initialization via `LLMFactory`, conversation memory, and token management.

**LLM Abstraction** (`src/agent/llm/`):
- `factory.py`: Creates LLM instances based on config
- `base.py`: Abstract base class with rate limiting
- Provider implementations: `claude_llm.py`, `openai_llm.py`, `gemini_llm.py`, `huggingface_llm.py`
- `rate_limiter.py`: Token-based rate limiting and cost tracking

**Agent Tools** (`src/agent/tool/`):
- `ast.py`: AST-based code analysis (`ASTNodeAnalyzer`)
- `internal_traverse.py`: Codebase traversal for finding callers/callees
- `perplexity_api.py`: External web search integration

**2. Dependency Analysis (`src/dependency_analyzer/`)**

Builds and processes import dependency graphs:
- `ast_parser.py`: Parses Python files into `CodeComponent` objects (functions, classes, methods)
- `topo_sort.py`: Implements dependency-first DFS traversal
- `__init__.py`: Exports `DependencyParser`, `dependency_first_dfs`, `build_graph_from_components`

**Key Insight**: The dependency graph edge `A→B` means "A depends on B", so DFS starts from components with no dependencies (roots) and processes dependencies before dependents.

**3. Evaluation System (`src/evaluator/`)**

Evaluates docstring quality across multiple dimensions:
- `completeness.py`: Checks if all parameters/returns/raises are documented (AST-based)
- `helpfulness_*.py`: Various helpfulness evaluators (summary, parameters, examples, attributes, description)
- `truthfulness.py`: Verifies docstrings match actual code behavior
- `segment.py`: Segments docstrings into components for fine-grained evaluation
- `helper/context_finder.py`: Finds relevant code context for evaluation

**4. Visualization & Progress (`src/visualizer/`)**

- `progress.py`: Terminal-based progress visualization during generation
- `status.py`: Status tracking for components
- `web_bridge.py`: Integration with web UI via SocketIO

**5. Web Interfaces**

**Generation UI** (`src/web/`):
- `app.py`: Flask application
- `process_handler.py`: Manages generation subprocess
- `config_handler.py`: Configuration management
- `visualization_handler.py`: Real-time progress updates via WebSocket

**Evaluation UI** (`src/web_eval/`):
- `app.py`: Flask application for docstring evaluation
- `helpers.py`: Google-style docstring parser
- `test_docstring_parser.py`: Test cases (run directly, not via pytest)

### Entry Points

- `generate_docstrings.py`: Main CLI for generation
- `run_web_ui.py`: Launch generation web interface
- `src/web_eval/app.py`: Launch evaluation web interface
- `eval_completeness.py`: Standalone completeness evaluation

### Data Flow

1. **Parsing Phase**: `DependencyParser` scans repository → creates `CodeComponent` objects → builds dependency graph
2. **Ordering Phase**: `dependency_first_dfs` produces processing order (or random modes)
3. **Generation Phase**: For each component:
   - `Orchestrator.process()` initiated
   - `Reader` assesses context needs
   - `Searcher` gathers context (internal AST traversal or external search)
   - `Writer` generates docstring
   - `Verifier` evaluates and may trigger revision loop
4. **Insertion Phase**: `set_docstring_in_file()` updates source code via AST manipulation
5. **Re-parsing**: File re-parsed if more components remain (line numbers change)

### Important Patterns

**AST Manipulation:**
- Code uses `ast.parse()` and `ast.unparse()` (or `astor` for Python < 3.9)
- `set_node_docstring()` handles indentation and triple-quote formatting
- Components must be located in AST tree by matching names/types

**Test Mode:**
- `--test-mode placeholder`: No LLM calls, generates test docstrings
- `--test-mode context_print`: Prints context for debugging
- `--test-mode none`: Normal operation (default)

**Component Filtering:**
- `__init__` methods are skipped (don't need docstrings)
- Components with existing docstrings skipped unless `--overwrite-docstrings` or config `docstring_options.overwrite_docstrings: true`
- Components > 10,000 tokens are truncated

**Rate Limiting:**
- Each LLM has configured rate limits (requests/min, tokens/min)
- Automatic cost tracking per provider
- Statistics printed at end of generation

## Common Workflows

### Adding a New Test
Create test files that don't start with `test_` as the filename, or if they do, ensure test functions use proper pytest fixtures or don't have parameters. Helper functions called from `main()` should not start with `test_`.

### Modifying Agent Behavior
1. Agent prompts are typically in the agent class methods
2. Inherit from `BaseAgent` for consistency
3. Use `self.generate_response()` for LLM calls
4. Update `config/example_config.yaml` if adding new parameters

### Adding LLM Provider
1. Create new file in `src/agent/llm/` (e.g., `custom_llm.py`)
2. Inherit from `BaseLLM` in `base.py`
3. Implement `generate()` method
4. Register in `LLMFactory` in `factory.py`
5. Add rate limits to config

### Debugging Generation Issues
1. Use `--test-mode context_print` to see what context is being used
2. Check `output/dependency_graphs/` for dependency graph JSON
3. Enable web UI (`--enable-web`) for real-time visualization
4. Review LLM rate limiter statistics at end of run

## File Organization

- `src/agent/`: Multi-agent system core
- `src/dependency_analyzer/`: Dependency graph construction
- `src/evaluator/`: Docstring quality evaluation
- `src/visualizer/`: Progress visualization
- `src/web/`: Generation web UI
- `src/web_eval/`: Evaluation web UI
- `src/data/parse/`: Data processing utilities
- `config/`: Configuration files (must create `agent_config.yaml`)
- `data/`: Test repositories
- `tool/`: Utility scripts
- `output/`: Generated files (dependency graphs, results)

## Testing Considerations

- Web UI components require `eventlet` monkey patching (imported before other modules)
- Ensure eventlet patching occurs in `src/web/app.py` and `src/web_eval/app.py` before imports
- The codebase uses Python 3.8+ (3.10+ recommended)
- Google-style docstrings are the standard format
