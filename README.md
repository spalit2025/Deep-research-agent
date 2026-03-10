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

  - **4 report templates**: Business, Academic, Technical, and Quick -- each with
    tailored structure, token budgets, and prompt strategies
  - **Prompt versioning & A/B testing**: Create, compare, and track prompt
    performance with built-in analytics
  - **Smart search caching**: Query similarity detection reduces redundant API
    calls (70-90% hit rate)
  - **Token management**: Automatic content fitting for Claude's context window
  - **Robust output parsing**: Multi-strategy JSON extraction handles varied LLM
    response formats

  ## Quick start

  ```bash
  # Clone and install
  git clone https://github.com/spalit2025/Deep-research-agent.git
  cd Deep-research-agent
  pip install -e .[dev]

  # Set up API keys
  cp env_template.sh .env
  # Edit .env with your ANTHROPIC_API_KEY and TAVILY_API_KEY

  # Generate a report
  deep-research --topic "AI in healthcare" --template business
  deep-research --topic "quantum computing" --template academic
  deep-research --topic "renewable energy" --template quick
  ```

 ## Architecture                                           

  ```
  User Input (CLI)
      |
  ReportConfig (template selection)
      |
  ImprovedReportGenerator
      ├── Plan report structure (template-specific prompts)
      ├── Research sections (Tavily API, cached via SearchCache)
      ├── Write sections (Claude API, rate-limited)
      |   └── TokenManager fits source content to context window
      └── Compile final report
  ```

  ## Core modules:

  - `report_generator.py` -- Main orchestrator: plans, researches, writes, compiles
  - `config.py` -- Template presets with token limits, caching, and rate limiting config
  - `utils/search_cache.py` -- Query caching with similarity detection
  - `utils/prompt_versioning.py` -- Version management, A/B testing, performance analytics
  - `utils/token_manager.py` -- Fits content to 200k token context window
  - `utils/json_parser.py` -- Multi-strategy JSON extraction from LLM responses
  - `utils/prompt_loader.py` -- Template-aware prompt loading with versioning support


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

  - **Similarity-based caching** over exact-match: Research queries on the same topic use slightly different phrasing. Similarity detection (threshold: 0.75)
  catches these, dramatically improving cache hit rates vs. exact matching.

  - **Template-specific token budgets**: A quick report and an academic report have different depth requirements. Each template defines its own token
  allocation rather than using a global limit.

  - **Prompt versioning as a first-class feature**: Instead of editing prompts in-place and hoping they improve, every change is versioned with analytics.
  This mirrors how production ML teams manage model versions.

  - **Graceful degradation**: Rate limiting, retry logic, and multi-strategy JSON parsing mean the system handles API hiccups without crashing.  

 ## Configuration                                                                                     
   
  Key settings in `config.py`:                                                                         
                                                            
  ```python
  ReportConfig(
      template="business",           # business | academic | technical | quick
      max_content_length=200000,     # Token budget
      enable_search_caching=True,    # Smart caching
      cache_ttl_hours=24.0,          # Cache expiration
      similarity_threshold=0.75,     # Cache similarity matching
      enable_prompt_versioning=True, # A/B testing system
  )
  ```


  ## Requirements

  - Python 3.8+
  - https://console.anthropic.com/ (Claude)
  - https://tavily.com/ (web search)

  ## License

  MIT
