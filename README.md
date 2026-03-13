# Deep Research Agent

  Research report creation is manual, time-consuming, and inconsistent. A typical
  report requires hours of searching, reading, synthesizing, and formatting -- and
  the quality varies every time.

  Deep Research Agent automates the full pipeline from web search to structured
  report. Give it a topic and a template, and it produces a publication-ready
  document in minutes. Built with Claude for generation, Tavily for web research,
  and a custom prompt versioning system that lets you A/B test prompt strategies
  and track quality over time.

  ## Why I built this

  I wanted to explore three product questions:
  1. **Can you make AI output quality measurable?** The prompt versioning system
     tracks success rates, quality scores, and execution times across prompt
     versions -- turning "this prompt feels better" into data.
  2. **How do you manage cost at scale?** Smart caching with similarity detection
     achieves 70-90% cache hit rates on subsequent runs, cutting API costs
     significantly.
  3. **What does "production-ready" look like for an AI pipeline?** Rate limiting,
     robust JSON parsing, token management for context windows, and template-specific
     optimization.

  ## Key capabilities

  - **5 report templates**: Standard, Business, Academic, Technical, and Quick --
    each with tailored structure, token budgets, and prompt strategies
  - **Prompt versioning & A/B testing**: Create, compare, and track prompt
    performance with built-in analytics
  - **Smart search caching**: Query similarity detection reduces redundant API
    calls (70-90% hit rate)
  - **Token management**: Automatic content fitting for Claude's context window
  - **Robust output parsing**: Multi-strategy JSON extraction handles varied LLM
    response formats
  - **Structured observability**: Correlation IDs, structured JSON logging, and
    performance metrics via structlog

  ## Quick start

  ```bash
  # Clone and install
  git clone https://github.com/spalit2025/Deep-research-agent.git
  cd Deep-research-agent
  pip install -r requirements.txt

  # Set up API keys
  cp env_template.sh .env
  # Edit .env with your ANTHROPIC_API_KEY and TAVILY_API_KEY

  # Generate a report (interactive mode)
  python main.py

  # Generate a single report
  python main.py "AI in healthcare" -t business
  python main.py "quantum computing" --template academic
  python main.py "renewable energy" -t quick
  ```

  ### Environment variables

  | Variable | Required | Description |
  |----------|----------|-------------|
  | `ANTHROPIC_API_KEY` | Yes | Claude API key from [console.anthropic.com](https://console.anthropic.com/) |
  | `TAVILY_API_KEY` | Yes | Tavily search API key from [tavily.com](https://tavily.com/) |
  | `MODEL_NAME` | No | Override default Claude model (default: `claude-sonnet-4-20250514`) |

 ## Architecture

  ```
  CLI (argparse)
      |
  main.py ── interactive_mode() or single_report_mode()
      |
  ReportConfig (template selection + MODEL_NAME env override)
      |
  ImprovedReportGenerator
      |
      |── _plan_report()
      |       └── _call_claude() ── Claude API (rate-limited)
      |              └── parse_report_plan() ── RobustJSONParser
      |
      |── _research_and_write_section()
      |       |── _generate_search_queries()
      |       |       └── _call_claude() ── Claude API
      |       |── _search_web()
      |       |       |── SearchCache (similarity-based, JSON persistence)
      |       |       └── Tavily API (rate-limited)
      |       └── _write_section_with_sources()
      |               |── TokenManager (context window optimization)
      |               └── _call_claude() ── Claude API
      |
      |── _write_contextual_section()
      |       └── _call_claude() ── Claude API
      |
      └── _compile_report() ── Markdown assembly
  ```

  ## Core modules

  | Module | Purpose |
  |--------|---------|
  | `main.py` | CLI entry point with argparse, interactive and single-report modes |
  | `report_generator.py` | Main orchestrator: plans, researches, writes, compiles |
  | `config.py` | Template presets with token limits, caching, and rate limiting config |
  | `utils/search_cache.py` | Query caching with similarity detection (JSON-backed) |
  | `utils/token_manager.py` | Fits content to 200k token context window |
  | `utils/json_parser.py` | Multi-strategy JSON extraction from LLM responses |
  | `utils/rate_limiter.py` | Rate limiting with exponential backoff retry |
  | `utils/observability.py` | Structured logging with correlation IDs via structlog |
  | `utils/prompt_loader.py` | Template-aware prompt loading with versioning support |
  | `utils/prompt_versioning.py` | Version management, A/B testing, performance analytics |


  ## Prompt versioning

  The system tracks prompt performance so you can make data-driven decisions
  about prompt quality:

  ```bash
  python prompt_cli.py list                                    # List all versions
  python prompt_cli.py analytics -p SECTION_WRITER_PROMPT     # View performance data
  python prompt_cli.py add SECTION_WRITER_PROMPT v2.0 "..." -d "Better formatting"
  python prompt_cli.py set-active SECTION_WRITER_PROMPT v2.0  # Switch active version
  python prompt_cli.py test SECTION_WRITER_PROMPT v2.0 "AI in healthcare"
  ```

  ## Key design decisions

  - **Similarity-based caching** over exact-match: Research queries on the same
    topic use slightly different phrasing. Similarity detection (threshold: 0.75)
    catches these, dramatically improving cache hit rates vs. exact matching.

  - **Template-specific token budgets**: A quick report and an academic report
    have different depth requirements. Each template defines its own token
    allocation rather than using a global limit.

  - **Prompt versioning as a first-class feature**: Instead of editing prompts
    in-place and hoping they improve, every change is versioned with analytics.
    This mirrors how production ML teams manage model versions.

  - **Graceful degradation**: Rate limiting, retry logic, and multi-strategy JSON
    parsing mean the system handles API hiccups without crashing. Every Claude API
    call routes through a single `_call_claude()` helper with empty-response
    validation.

  - **JSON cache serialization**: Cache files use JSON instead of pickle to
    eliminate arbitrary code execution risk from user-writable cache directories.

 ## Configuration

  Key settings in `config.py`:

  ```python
  ReportConfig(
      template="business",           # standard | business | academic | technical | quick
      enable_search_caching=True,    # Smart caching
      cache_ttl_hours=24.0,          # Cache expiration
      similarity_threshold=0.75,     # Cache similarity matching
      enable_prompt_versioning=True, # A/B testing system
  )
  ```

  ## Testing

  ```bash
  # Run all tests
  pytest tests/ -v

  # Run with coverage
  pytest tests/ --cov=. --cov-report=term-missing
  ```

  151 tests covering report generation, config, search cache, JSON parsing,
  rate limiting, and CLI argument parsing.

  ## Contributing

  1. Fork the repo and create a feature branch
  2. Install dev dependencies: `pip install -r requirements.txt`
  3. Make your changes and add tests
  4. Run `ruff check .` and `pytest tests/` before submitting
  5. Open a pull request against `main`

  ## Requirements

  - Python 3.10+
  - [Anthropic API key](https://console.anthropic.com/) (Claude)
  - [Tavily API key](https://tavily.com/) (web search)

  ## License

  MIT
