import os
import json
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
@dataclass
class Config:
    """Configuration for the evaluation script"""
    data_path: Path = Path("data/dev_turn.json")
    model_name: str = "gpt-4o"
    max_dialogues: Optional[int] = 100
    sleep_between_calls: float = 1.0
    results_file: Path = Path("results.txt")
    temperature: float = 0.1
    relative_tolerance: float = 1e-3
    absolute_tolerance: float = 1e-4


# ------------------------------------------------------------
# System Prompt Loading
# ------------------------------------------------------------
def load_system_prompt() -> str:
    """
    Load system prompt from external file.
    
    Returns:
        System prompt template string
    """
    prompt_file = Path(__file__).parent / "system_prompt.txt"
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"System prompt file not found: {prompt_file}")
    except Exception as e:
        raise RuntimeError(f"Failed to load system prompt: {e}") from e


# ------------------------------------------------------------
# Custom Exceptions
# ------------------------------------------------------------
class APIError(Exception):
    """Custom exception for API-related errors"""
    pass


class JSONParsingError(Exception):
    """Custom exception for JSON parsing errors"""
    pass


# ------------------------------------------------------------
# Logging Setup
# ------------------------------------------------------------
def setup_logging(log_file: Path) -> Tuple[logging.Logger, logging.FileHandler]:
    """
    Setup logging to both console and file.
    
    Args:
        log_file: Path to the log file
        
    Returns:
        Tuple of (logger, file_handler)
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger, file_handler


# ------------------------------------------------------------
# Conversation Memory Class
# ------------------------------------------------------------
class ConversationMemory:
    """Manage conversation history for multi-turn dialogues"""
    
    def __init__(self, system_prompt: Optional[str] = None):
        """
        Initialize conversation memory.
        
        Args:
            system_prompt: Optional system prompt to use for this conversation
        """
        self._messages: List[Dict[str, str]] = []
        self._system_prompt: Optional[str] = system_prompt
    
    def set_system_prompt(self, prompt: str) -> None:
        """Set the system prompt for this conversation"""
        self._system_prompt = prompt
    
    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.
        
        Args:
            role: Message role (user, assistant, or system)
            content: Message content
            
        Raises:
            ValueError: If role is invalid
        """
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {role}. Must be 'user', 'assistant', or 'system'")
        self._messages.append({"role": role, "content": content})
    
    def add_user_message(self, message: str) -> None:
        """Add user message to memory"""
        self.add_message("user", message)
    
    def add_assistant_message(self, message: str) -> None:
        """Add assistant message to memory"""
        self.add_message("assistant", message)
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get full conversation history including system prompt"""
        history = []
        if self._system_prompt:
            history.append({"role": "system", "content": self._system_prompt})
        return history + self._messages
    
    def clear(self) -> None:
        """Clear conversation memory"""
        self._messages.clear()
        self._system_prompt = None
    
    def __len__(self) -> int:
        """Return number of messages in memory"""
        return len(self._messages)
    
    def __repr__(self) -> str:
        return f"ConversationMemory(messages={len(self._messages)}, has_system_prompt={self._system_prompt is not None})"


# ------------------------------------------------------------
# Dialogue Processing
# ------------------------------------------------------------
class DialogueProcessor:
    """Process and organize dialogue data"""
    
    @staticmethod
    def extract_dialogue_id(full_id: str) -> str:
        """
        Extract base dialogue ID from full ID.
        
        Args:
            full_id: Full dialogue ID with turn index (e.g., "dialogue_1_0")
            
        Returns:
            Base dialogue ID without turn index (e.g., "dialogue_1")
        """
        parts = full_id.split('_')
        if parts[-1].isdigit():
            return '_'.join(parts[:-1])
        return full_id
    
    @staticmethod
    def group_by_dialogue(data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group data entries by dialogue ID and sort by turn.
        
        Args:
            data: List of dialogue turn data
            
        Returns:
            Dictionary mapping dialogue IDs to sorted lists of turns
        """
        dialogues = defaultdict(list)
        
        for item in data:
            dialogue_id = DialogueProcessor.extract_dialogue_id(item["id"])
            dialogues[dialogue_id].append(item)
        
        # Sort each dialogue by turn_ind
        for dialogue_id in dialogues:
            dialogues[dialogue_id].sort(key=lambda x: x["annotation"]["turn_ind"])
        
        return dict(dialogues)
    
    @staticmethod
    def extract_document_context(turn_data: Dict[str, Any]) -> str:
        """
        Extract document context from turn data.
        
        Args:
            turn_data: Single turn data containing annotations
            
        Returns:
            Formatted document context string
        """
        annotation = turn_data["annotation"]
        table_html = annotation["amt_table"]
        pre_text = annotation.get("amt_pre_text", "")
        post_text = annotation.get("amt_post_text", "")
        
        return f"""Text before table:
                {pre_text}

                HTML Table:
                {table_html}

                Text after table:
                {post_text}""".strip()
    
    @staticmethod
    def extract_questions_and_answers(dialogue_turns: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
        """
        Extract questions and gold answers from dialogue turns.
        
        Args:
            dialogue_turns: List of turns in a dialogue
            
        Returns:
            Tuple of (questions list, gold answers list)
        """
        questions = []
        gold_answers = []
        
        for turn in dialogue_turns:
            turn_annotation = turn["annotation"]
            dialogue_break = turn_annotation["dialogue_break"]
            turn_ind = turn_annotation["turn_ind"]
            question = dialogue_break[turn_ind]
            
            questions.append(question)
            gold_answers.append(str(turn_annotation["exe_ans"]))
        
        return questions, gold_answers


# ------------------------------------------------------------
# Results Tracking
# ------------------------------------------------------------
@dataclass
class EvaluationResults:
    """Track evaluation metrics"""
    total_correct: int = 0
    total_questions: int = 0
    total_errors: int = 0
    dialogue_results: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def accuracy(self) -> float:
        """Calculate overall accuracy"""
        return self.total_correct / self.total_questions if self.total_questions > 0 else 0.0
    
    def add_dialogue_result(self, dialogue_id: str, correct: int, 
                           total: int, errors: int) -> None:
        """
        Add results for a single dialogue.
        
        Args:
            dialogue_id: Identifier for the dialogue
            correct: Number of correct answers
            total: Total number of questions
            errors: Number of errors encountered
        """
        self.total_correct += correct
        self.total_questions += total
        self.total_errors += errors
        self.dialogue_results.append({
            "dialogue_id": dialogue_id,
            "correct": correct,
            "total": total,
            "errors": errors,
            "accuracy": correct / total if total > 0 else 0.0
        })


# ------------------------------------------------------------
# Answer Comparison
# ------------------------------------------------------------
def normalize_answer(x: Any) -> float:
    """
    Convert answer to float for numeric comparison.
    
    Args:
        x: Answer value to normalize
        
    Returns:
        Normalized float value, 0.0 if conversion fails
    """
    if x is None:
        return 0.0
    x_str = str(x).strip().lower()
    x_str = x_str.replace(" ", "").replace("$", "").replace("%", "")
    try:
        return float(x_str)
    except ValueError:
        print(f"Warning: Could not convert '{x}'")
        return 0.0


def answers_match(pred: Any, gold: Any, 
                  relative_tolerance: float = 1e-3, 
                  absolute_tolerance: float = 1e-4) -> bool:
    """
    Compare predicted and gold answers with numeric tolerance.
    
    Args:
        pred: Predicted answer
        gold: Gold standard answer
        relative_tolerance: Maximum relative difference allowed
        absolute_tolerance: Maximum absolute difference allowed
        
    Returns:
        True if answers match within tolerance, False otherwise
    """
    pred_num = normalize_answer(pred)
    gold_num = normalize_answer(gold)
    abs_diff = abs(pred_num - gold_num)
    rel_diff = abs_diff / max(abs(gold_num), 1e-10)
    return abs_diff <= absolute_tolerance or rel_diff <= relative_tolerance


# ------------------------------------------------------------
# Response Parsing
# ------------------------------------------------------------
def parse_llm_response(response_text: str) -> Dict[str, Any]:
    """
    Parse and clean LLM response, extracting JSON.
    
    Args:
        response_text: Raw response text from LLM
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        JSONParsingError: If JSON parsing fails
    """
    try:
        # Strip markdown code blocks
        cleaned = response_text.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        raise JSONParsingError(f"Failed to parse JSON: {e}") from e


# ------------------------------------------------------------
# Main Evaluator Class
# ------------------------------------------------------------
class FinancialReasoningEvaluator:
    """Main evaluator class for financial reasoning tasks"""
    
    def __init__(self, config: Config, logger: logging.Logger):
        """
        Initialize the evaluator.
        
        Args:
            config: Configuration object
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.processor = DialogueProcessor()
    
    def load_data(self) -> List[Dict[str, Any]]:
        """
        Load evaluation data from JSON file.
        
        Returns:
            List of dialogue turn data
        """
        with open(self.config.data_path, encoding='utf-8') as f:
            return json.load(f)
    
    def build_system_prompt(self, document_context: str) -> str:
        """
        Build complete system prompt with document context.
        
        Args:
            document_context: Financial document context to include
            
        Returns:
            Complete system prompt string
        """
        system_prompt_template = load_system_prompt()
        return f"""{system_prompt_template}

Financial Document Content:
{document_context}

I will ask you multiple questions about this document. Please answer each question with the specified JSON format."""
    
    def process_dialogue(self, document_context: str, 
                        questions: List[str], 
                        gold_answers: List[str]) -> List[Dict[str, Any]]:
        """
        Process entire dialogue using conversation memory.
        
        Args:
            document_context: Financial document context
            questions: List of questions to ask
            gold_answers: List of gold standard answers
            
        Returns:
            List of response dictionaries for each question
        """
        # Initialize conversation memory
        memory = ConversationMemory()
        system_prompt = self.build_system_prompt(document_context)
        memory.set_system_prompt(system_prompt)
        
        responses = []
        
        for i, question in enumerate(questions):
            try:
                # Add current question to memory
                question_text = f"Question: {question}\n\nReturn only JSON:"
                memory.add_user_message(question_text)
                
                # Get full conversation history
                messages = memory.get_conversation_history()
                
                # Call OpenAI API
                response = self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    temperature=self.config.temperature
                )
                
                response_text = response.choices[0].message.content
                if not response_text:
                    raise ValueError("Empty response from LLM API")
                
                # Parse JSON response
                result = parse_llm_response(response_text)
                responses.append(result)
                
                # Add assistant response to memory
                memory.add_assistant_message(response_text)
                
                # Show detailed output during processing
                pred = result.get("answer", "")
                gold = gold_answers[i]
                is_correct = answers_match(pred, gold, 
                                          self.config.relative_tolerance,
                                          self.config.absolute_tolerance)
                
                self.logger.info(f"  Turn {i+1}: Q: {question}")
                self.logger.info(f"  Turn {i+1}: Pred: {pred}")
                self.logger.info(f"  Turn {i+1}: Gold: {gold}")
                self.logger.info(f"  Turn {i+1}: Match: {is_correct}")
                self.logger.info(f"  Turn {i+1}: Details: {result}")
                self.logger.info(f"  Turn {i+1}: Memory has {len(memory)} messages")
                self.logger.info("")
                
            except JSONParsingError as e:
                self.logger.error(f"JSON parsing error for question {i+1}: {e}")
                self.logger.error(f"Raw response: {response_text}")
                responses.append({"error": str(e)})
                memory.add_assistant_message(f"Error: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"OpenAI API error for question {i+1}: {e}")
                responses.append({"error": str(e)})
                memory.add_assistant_message(f"Error: {str(e)}")
            
            time.sleep(self.config.sleep_between_calls)
        
        # Print memory summary
        self.logger.info(f"  Conversation memory contains {len(memory)} messages")
        
        # Clear memory for next dialogue
        memory.clear()
        self.logger.info("  Memory cleared for next dialogue")
        
        return responses
    
    def evaluate_dialogue(self, dialogue_id: str, 
                         dialogue_turns: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Evaluate a single dialogue.
        
        Args:
            dialogue_id: Identifier for the dialogue
            dialogue_turns: List of turns in the dialogue
            
        Returns:
            Tuple of (correct_count, error_count)
        """
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"Processing Dialogue: {dialogue_id}")
        self.logger.info(f"Number of turns: {len(dialogue_turns)}")
        self.logger.info(f"{'='*80}")
        
        # Extract document context and questions
        document_context = self.processor.extract_document_context(dialogue_turns[0])
        questions, gold_answers = self.processor.extract_questions_and_answers(dialogue_turns)
        
        # Process entire conversation
        self.logger.info(f"Starting conversation with {len(questions)} questions...")
        responses = self.process_dialogue(document_context, questions, gold_answers)
        
        # Evaluate each turn
        dialogue_correct = 0
        dialogue_errors = 0
        
        for i, (response, gold) in enumerate(zip(responses, gold_answers)):
            if "error" in response:
                dialogue_errors += 1
            else:
                pred = response.get("answer", "")
                if answers_match(pred, gold, 
                               self.config.relative_tolerance,
                               self.config.absolute_tolerance):
                    dialogue_correct += 1
        
        self.logger.info(f"Dialogue {dialogue_id} Results:")
        self.logger.info(f"  Correct: {dialogue_correct}/{len(questions)}")
        self.logger.info(f"  Errors: {dialogue_errors}")
        self.logger.info(f"  Accuracy: {dialogue_correct/len(questions):.2%}")
        
        return dialogue_correct, dialogue_errors
    
    def evaluate(self) -> EvaluationResults:
        """
        Run full evaluation and return results.
        
        Returns:
            EvaluationResults object with complete metrics
        """
        # Load and process data
        data = self.load_data()
        dialogues = self.processor.group_by_dialogue(data)
        dialogue_ids = list(dialogues.keys())
        
        if self.config.max_dialogues is not None:
            dialogue_ids = dialogue_ids[:self.config.max_dialogues]
        
        results = EvaluationResults()
        
        self.logger.info(f"Using OpenAI {self.config.model_name} with custom memory")
        self.logger.info(f"Processing {len(dialogue_ids)} dialogues with memory management")
        self.logger.info(f"Results will be saved to: {self.config.results_file}")
        
        # Evaluate each dialogue
        for dialogue_id in dialogue_ids:
            dialogue_turns = dialogues[dialogue_id]
            correct, errors = self.evaluate_dialogue(dialogue_id, dialogue_turns)
            results.add_dialogue_result(dialogue_id, correct, len(dialogue_turns), errors)
        
        # Log final results
        self.logger.info(f"\n{'='*80}")
        self.logger.info("FINAL RESULTS")
        self.logger.info(f"{'='*80}")
        self.logger.info(f"OpenAI Model: {self.config.model_name}")
        self.logger.info(f"Memory Type: Custom ConversationMemory Class")
        self.logger.info(f"Total Dialogues: {len(dialogue_ids)}")
        self.logger.info(f"Total Questions: {results.total_questions}")
        self.logger.info(f"Total Correct: {results.total_correct}")
        self.logger.info(f"Total Errors: {results.total_errors}")
        if results.total_questions > 0:
            self.logger.info(f"Overall Accuracy: {results.accuracy:.2%}")
        
        return results


# ------------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------------
def main() -> None:
    """Main entry point for the evaluation script"""
    # Load environment variables
    load_dotenv()
    
    # Validate environment
    if "OPENAI_API_KEY" not in os.environ:
        raise RuntimeError("OPENAI_API_KEY environment variable not set.")
    
    # Setup
    config = Config()
    logger, file_handler = setup_logging(config.results_file)
    
    try:
        # Run evaluation
        evaluator = FinancialReasoningEvaluator(config, logger)
        results = evaluator.evaluate()
        
        # Log completion
        logger.info(f"\nResults saved to: {config.results_file}")
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        if file_handler:
            file_handler.close()
            logger.removeHandler(file_handler)


if __name__ == "__main__":
    main()