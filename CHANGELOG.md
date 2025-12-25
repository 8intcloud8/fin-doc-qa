# Changelog

All notable changes to the ConvFinQA Evaluator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-12-25

### Added
- Initial release of ConvFinQA Evaluator
- Support for GPT-4o model integration
- Conversational memory management system
- Custom system prompt with financial reasoning rules
- JSON response parsing with error handling
- Tolerance-based answer validation
- Comprehensive logging to both console and file
- Support for multi-turn financial dialogues
- Structured project architecture with dataclasses
- External system prompt configuration
- Unit conversion handling for financial data
- Percentage calculation standardization

### Features
- **Multi-turn Conversations**: Maintains context across question sequences
- **Financial Reasoning**: Specialized prompts for financial document analysis
- **Robust Parsing**: Handles markdown-wrapped JSON responses
- **Accuracy Tracking**: Detailed metrics with tolerance-based matching
- **Error Recovery**: Graceful handling of API and parsing errors
- **Configurable Models**: Easy switching between different LLM models
- **Comprehensive Logging**: Detailed output for debugging and analysis

### Technical Details
- Python 3.8+ compatibility
- OpenAI API integration
- Dataclass-based configuration
- Type hints throughout codebase
- Modular architecture for easy extension
- External prompt configuration for easy iteration

### Documentation
- Comprehensive README with presentation-style formatting
- Detailed setup instructions
- Configuration examples
- Usage guidelines
- Contributing guidelines
- MIT License

### Known Issues
- Some dataset annotations contain unit conversion errors
- Occasional JSON formatting inconsistencies from LLM responses
- Performance varies with different financial document structures

## [Unreleased]

### Planned
- Support for additional LLM providers (Anthropic Claude, Google Gemini)
- Enhanced unit conversion handling
- Batch processing capabilities
- Result visualization tools
- Performance optimization
- Extended test coverage