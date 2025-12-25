# 🏦 LLMConvFinQA: Conversational Financial Question Answering

**An LLM-powered system for multi-turn financial document analysis with conversational memory.**


---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Dataset Structure](#dataset-structure)
- [System Architecture](#system-architecture)
- [Configuration](#configuration)
- [Example Output](#example-output)
- [Performance Metrics](#performance-metrics)
- [Project Structure](#project-structure)
- [Technical Details](#technical-details)
- [Dependencies](#dependencies)
- [License](#license)
- [Citation](#citation)

---

## Overview

This system processes financial documents containing tables and text to answer complex questions through multi-turn dialogues. Unlike traditional QA systems, it maintains conversational context—enabling follow-up questions that reference previous answers.

**Example Conversation:**
```
Q1: "What was the price in 2007?"        → 60.94
Q2: "And in 2005?"                       → 25.14
Q3: "What was the change?"               → 35.8 (calculated from previous answers)
Q4: "What's the percentage change?"      → 142.4% (multi-step reasoning)
```

---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **📊 Financial Document Processing** | Parses HTML tables with surrounding contextual text |
| **🧠 Conversational Memory** | Maintains complete dialogue history across turns |
| **🔢 Mathematical Reasoning** | Performs calculations, comparisons, and percentage changes |
| **✅ Answer Validation** | Tolerance-based matching (relative: 0.1%, absolute: 0.0001) |
| **📝 Comprehensive Logging** | Saves detailed conversation traces to file |


---

## Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd llmconvfinqa

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### Running the System
```bash
python src/main.py
```

**Output**: Results are displayed in console and saved to `results.txt`

---

## Dataset Structure

### ConvFinQA Dataset Overview

- **Total Entries**: ~1,490 question-answer pairs
- **Dialogues**: ~421 conversational sequences
- **Average Length**: 3.5 turns per dialogue
- **Format**: JSON with structured annotations

### Data Entry Format

Each entry represents one turn in a conversation:
```json
{
  "id": "Single_MRO/2007/page_134.pdf-1_0",
  "filename": "MRO/2007/page_134.pdf",
  "annotation": {
    "amt_table": "<table>...</table>",
    "amt_pre_text": "Text before table",
    "amt_post_text": "Text after table",
    "dialogue_break": ["Q1", "Q2", "Q3"],
    "exe_ans": 60.94,
    "turn_ind": 0
  }
}
```

### Key Fields

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique identifier (dialogue + turn) | `"doc-1_0"` (dialogue 1, turn 0) |
| `amt_table` | Financial table (HTML) | `<table>...</table>` |
| `amt_pre_text` | Context before table | Background information |
| `amt_post_text` | Context after table | Additional notes |
| `dialogue_break` | List of questions in order | `["Q1", "Q2", "Q3"]` |
| `exe_ans` | Expected answer | `60.94` |
| `turn_ind` | Turn index (0-based) | `0`, `1`, `2` |

### Multi-Turn Example
```
Dialogue ID: Single_MRO/2007/page_134.pdf-1
├── Turn 0: "What was the price in 2007?" → 60.94
├── Turn 1: "And in 2005?" → 25.14
├── Turn 2: "What was the change?" → 35.8
└── Turn 3: "What's the percentage?" → 142.4
```

---

## System Architecture
```
┌─────────────────┐
│  ConvFinQA      │
│  Dataset        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Dialogue       │
│  Processor      │ ← Groups by dialogue, sorts by turn
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Document       │
│  Context        │ ← Combines table + text
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Conversation   │
│  Memory         │ ← Maintains history
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  OpenAI GPT-4o  │ ← Financial reasoning
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Answer         │
│  Validation     │ ← Numerical matching
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Results        │
│  Logging        │
└─────────────────┘
```

### Components

| Component | Responsibility |
|-----------|----------------|
| **DialogueProcessor** | Groups data by dialogue, extracts context |
| **ConversationMemory** | Stores message history for each dialogue |
| **FinancialReasoningEvaluator** | Orchestrates the evaluation pipeline |
| **Answer Validator** | Compares predicted vs. gold answers |
| **Logger** | Outputs results to console and file |

---

## Configuration

### Main Settings

Edit the `Config` class in `main.py`:
```python
@dataclass
class Config:
    data_path: Path = Path("data/dev_turn.json")  # Dataset location
    model_name: str = "gpt-4o"                     # OpenAI model
    max_dialogues: Optional[int] = 20              # Limit dialogues (None = all)
    sleep_between_calls: float = 1.0               # API rate limiting
    results_file: Path = Path("results.txt")       # Output file
    temperature: float = 0.1                       # LLM temperature
    relative_tolerance: float = 1e-3               # 0.1% tolerance
    absolute_tolerance: float = 1e-4               # Absolute tolerance
```

### System Prompt

The financial reasoning prompt is defined in `SYSTEM_PROMPT_TEMPLATE`. Key rules:

- Use only provided numbers (table, text, or question)
- Don't invent values
- Return JSON format: `{"used_cells": [...], "calculation": "...", "answer": "..."}`
- Show step-by-step calculations

---

## Example Output

### Console Output
```
================================================================================
Processing Dialogue: Single_MRO/2007/page_134.pdf-1
Number of turns: 5
================================================================================

  Turn 1: Q: What was the weighted average exercise price per share in 2007?
  Turn 1: Pred: 60.94
  Turn 1: Gold: 60.94
  Turn 1: Match: True
  Turn 1: Details: {'used_cells': ['60.94'], 'calculation': 'table lookup', 'answer': '60.94'}
  Turn 1: Memory has 2 messages

  Turn 2: Q: And what was it in 2005?
  Turn 2: Pred: 25.14
  Turn 2: Gold: 25.14
  Turn 2: Match: True
  Turn 2: Details: {'used_cells': ['25.14'], 'calculation': 'table lookup', 'answer': '25.14'}
  Turn 2: Memory has 4 messages

Dialogue Single_MRO/2007/page_134.pdf-1 Results:
  Correct: 5/5
  Errors: 0
  Accuracy: 100.00%


================================================================================
FINAL RESULTS
================================================================================
OpenAI Model: gpt-4o
Memory Type: Custom ConversationMemory Class
Total Dialogues: 100
Total Questions: 349
Total Correct: 269
Total Errors: 0
Overall Accuracy: 77.08%
```

---

## Performance Metrics

### Accuracy Validation

The system uses two tolerance levels for numerical comparison:

- **Absolute Tolerance**: `1e-4` (0.0001)
  - Example: 60.94 vs 60.9401 → Match ✅
  
- **Relative Tolerance**: `1e-3` (0.1%)
  - Example: 100 vs 100.09 → Match ✅ (0.09% difference)

### Evaluation Metrics

For each dialogue and overall:
- **Correct Answers**: Count of matches within tolerance
- **Total Questions**: Number of turns processed
- **Errors**: API or parsing failures
- **Accuracy**: Correct / Total (as percentage)

---

## Project Structure
```
llmconvfinqa/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── .env.example             # Environment template
├── .gitignore               # Git ignore rules
├── results.txt              # Output results
│
├── src/
│   └── main.py              # Main implementation
│
└── data/
    └── dev_turn.json        # ConvFinQA dataset
```

---

## Technical Details

### Conversational Memory

**Key Features:**
- Stores complete message history
- Includes system prompt with document context
- Clears between dialogues
- Provides message count tracking

### Answer Extraction

The LLM returns structured JSON:
```json
{
  "used_cells": ["60.94", "25.14"],
  "calculation": "60.94 - 25.14 = 35.8",
  "answer": "35.8"
}
```

### Error Handling

- **JSON Parsing**: Strips markdown code blocks, handles malformed responses
- **API Errors**: Logs errors, continues processing remaining questions
- **Missing Data**: Validates required fields, provides defaults

---

## Dependencies
```
openai>=1.0.0
python-dotenv>=0.19.0
```

Install with:
```bash
pip install openai python-dotenv
```


---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## Support

For issues or questions:
- Open an issue on GitHub
- Check existing documentation
- Review the code comments

---
