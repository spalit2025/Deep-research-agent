# Deep Research Agent

AI-powered research report generator that creates comprehensive, well-structured documents on any topic. The system leverages advanced web search, intelligent caching, smart token management, and prompt versioning to deliver high-quality research reports.

## 🚀 Key Features

- **Multiple Report Templates**: Business, Academic, Technical, Quick, and Standard formats
- **Advanced Search Integration**: Powered by Tavily API for comprehensive research
- **Smart Caching System**: Reduces API calls with intelligent query similarity detection
- **Token Management**: Optimized for Claude 3.5 Sonnet with automatic context window management
- **Prompt Versioning**: A/B test and track performance of different prompt versions
- **Rate Limiting**: Built-in protections against API service interruptions
- **Robust JSON Parsing**: Handles varied AI response formats gracefully

## 🆕 Prompt Versioning System

The system includes a comprehensive prompt versioning and analytics platform:

- **Version Management**: Create, manage, and switch between different prompt versions
- **Performance Analytics**: Track success rates, quality scores, and usage patterns
- **A/B Testing**: Test different prompt approaches and automatically identify best performers
- **Migration Tools**: Seamlessly migrate from static prompts to versioned system
- **CLI Management**: Command-line interface for prompt version operations

### Prompt Versioning Quick Start

```bash
# Initialize the versioning system
python initialize_prompt_versioning.py

# List all prompt versions
python prompt_cli.py list

# View analytics for a specific prompt
python prompt_cli.py analytics -p SECTION_WRITER_PROMPT

# Add a new prompt version
python prompt_cli.py add SECTION_WRITER_PROMPT v2.0 "Your improved prompt..." -d "Better formatting"

# Set active version
python prompt_cli.py set-active SECTION_WRITER_PROMPT v2.0

# Test a prompt version
python prompt_cli.py test SECTION_WRITER_PROMPT v2.0 "AI in healthcare"
```

## 🚀 Getting Started

Follow these steps to set up and run the project locally.

### 1. Clone the Repository

```bash
git clone https://github.com/spalit2025/Deep-research-agent.git
cd Deep-research-agent
```

### 2. Set Up Environment Variables

This project requires API keys for Anthropic and Tavily.

1.  Create a `.env` file in the project root by copying the template:
    ```bash
    cp env_template.sh .env
    ```
2.  Edit the `.env` file and add your API keys. Refer to [env_template.sh](./env_template.sh) for all required variables.
    ```
    ANTHROPIC_API_KEY="your_anthropic_api_key_here"
    TAVILY_API_KEY="your_tavily_api_key_here"
    ```

### 3. Install Dependencies

The project uses `pyproject.toml` to manage dependencies. To install the application and its development tools, run:

```bash
pip install -e .[dev]
```
This command installs all main dependencies plus the development dependencies specified in [pyproject.toml](./pyproject.toml).

### 4. Initialize Prompt Versioning (Optional)

If you plan to use the prompt versioning system, run the initialization script:
```bash
python initialize_prompt_versioning.py
```

## 📊 Usage

### Running the Report Generator

The primary way to run the application is via the `deep-research` command, which is an entry point defined in [pyproject.toml](./pyproject.toml).

```bash
# Generate a business report on "AI in healthcare"
deep-research --topic "AI in healthcare" --template business

# Generate an academic report with verbose output
deep-research --topic "quantum computing" --template academic --verbose
```

### Advanced Usage

```bash
# Generate a quick report
deep-research --topic "renewable energy" --template quick

# Generate with a custom configuration file
deep-research --topic "blockchain technology" --template business --config custom_config.json

# Use a specific prompt version (if versioning is active)
deep-research --topic "AI ethics" --template academic --prompt-version v2.0_enhanced
```

## 🏗️ System Architecture

### Core Components

1. **Report Generator** (`report_generator.py`): Main orchestrator for report generation
2. **Prompt System** (`utils/prompt_loader.py`): Manages prompt templates and versioning
3. **Search Engine** (`utils/search_cache.py`): Handles web search with intelligent caching
4. **Token Manager** (`utils/token_manager.py`): Optimizes content for AI model limits
5. **JSON Parser** (`utils/json_parser.py`): Robust parsing of AI responses

### Prompt Versioning System

- **Version Manager** (`utils/prompt_versioning.py`): Core versioning and analytics engine
- **CLI Tool** (`prompt_cli.py`): Command-line interface for management
- **Migration Tool** (`initialize_prompt_versioning.py`): Setup and migration utilities

## 📈 Performance Metrics

### Search Caching
- **Cache Hit Rate**: 70-90% on subsequent runs
- **API Call Reduction**: Significant cost savings
- **Response Time**: Near-instant for cached queries

### Token Management
- **Context Optimization**: Automatic content fitting for Claude 3.5 Sonnet
- **Template-Specific Limits**: Optimized for each report type
- **Real-time Monitoring**: Track token usage throughout generation

### Prompt Versioning
- **A/B Testing**: Compare prompt performance scientifically
- **Analytics Tracking**: Success rates, quality scores, execution times
- **Version Control**: Full history and rollback capabilities

## 🔧 Configuration

### Main Configuration (`config.py`)

```python
{
    "template": "business",           # Report template type
    "prompt_version": "v1.0_static",  # Active prompt version
    "max_content_length": 200000,     # Token management limit
    "enable_search_caching": True,    # Enable intelligent caching
    "enable_prompt_versioning": True, # Enable prompt versioning
    "enable_prompt_analytics": True,  # Track prompt performance
    "cache_ttl_hours": 24.0,         # Cache expiration time
    "similarity_threshold": 0.75      # Cache similarity matching
}
```

### Prompt Versioning Configuration

```python
{
    "prompt_versions_dir": "prompt_versions",  # Version storage directory
    "prompt_usage_log": "prompt_usage.json",  # Analytics log file
    "enable_prompt_analytics": True,          # Performance tracking
    "auto_suggest_best_prompts": False        # Auto-switch to best performers
}
```

## 📚 Report Templates

### Business Template
- Executive Summary
- Market Analysis
- Competitive Landscape
- Strategic Recommendations
- Financial Projections

### Academic Template
- Abstract
- Literature Review
- Methodology
- Results & Analysis
- Conclusions

### Technical Template
- Technical Overview
- Architecture Analysis
- Implementation Details
- Performance Metrics
- Best Practices

### Quick Template
- Condensed format
- Key findings focus
- Rapid generation
- Essential insights only

## 🔍 Search & Research

### Tavily Integration
- Advanced web search capabilities
- Academic and business source prioritization
- Real-time information gathering
- Source citation and verification

### Caching Strategy
- Query similarity detection
- Persistent and in-memory caching
- Configurable TTL and cache size
- Performance monitoring and reporting

## 🎯 Prompt Engineering

### Version Management
- Create and test multiple prompt versions
- Track performance metrics automatically
- A/B test different approaches
- Rollback to previous versions

### Analytics Dashboard
- Success rate tracking
- Quality score monitoring
- Usage pattern analysis
- Performance comparisons

### Best Practices
- Use semantic versioning (v1.0, v1.1, v2.0)
- Document changes in version descriptions
- Test thoroughly before setting as active
- Monitor performance metrics regularly

## 🔧 Development and Code Quality

This project uses a modern Python development stack with automated tools to ensure code quality, consistency, and correctness. All tool configurations are defined in [pyproject.toml](./pyproject.toml).

### Development Setup

1.  **Follow the Getting Started Guide**: First, complete the setup in the **Getting Started** section, including cloning the repo and installing dependencies with `pip install -e .[dev]`.

2.  **Install Pre-commit Hooks**:
    ```bash
    pre-commit install
    ```
    This will run `black`, `ruff`, and other checks automatically every time you commit changes, enforcing the project's coding standards.

### Code Quality Tools

The following tools are used to maintain code quality:

- **Formatting**: `black` for consistent code style.
- **Linting**: `ruff` for fast and comprehensive code analysis.
- **Type Checking**: `mypy` for static type checking.

All tools are configured in `pyproject.toml` and are run automatically via the pre-commit hooks.

## 🤝 Contributing

1. Fork the repository
2. Run `./setup_dev.sh` to set up development environment
3. Create a feature branch
4. Make changes following code quality standards
5. Test your changes thoroughly (pre-commit hooks will run automatically)
6. Submit a pull request with detailed description

All contributions should follow the established code quality standards.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---
**Note**: This system requires API keys for Anthropic (Claude) and Tavily. Ensure you have appropriate usage limits and billing set up for production use.
