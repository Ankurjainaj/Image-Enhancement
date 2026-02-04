"""
Centralized Logging Configuration
Provides structured logging for the entire application
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log format with detailed information
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Color codes for console output
COLORS = {
    'DEBUG': '\033[36m',      # Cyan
    'INFO': '\033[32m',       # Green
    'WARNING': '\033[33m',    # Yellow
    'ERROR': '\033[31m',      # Red
    'CRITICAL': '\033[35m',   # Magenta
    'RESET': '\033[0m'
}


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if levelname in COLORS:
            record.levelname = f"{COLORS[levelname]}{levelname}{COLORS['RESET']}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True
) -> None:
    """
    Setup logging configuration for the entire application
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler with colors
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_formatter = ColoredFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handler - main log
    if log_to_file:
        today = datetime.now().strftime("%Y-%m-%d")
        file_handler = logging.FileHandler(
            LOGS_DIR / f"app_{today}.log",
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Separate file for errors
        error_handler = logging.FileHandler(
            LOGS_DIR / f"errors_{today}.log",
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        # Separate file for Bedrock calls
        bedrock_handler = logging.FileHandler(
            LOGS_DIR / f"bedrock_{today}.log",
            encoding='utf-8'
        )
        bedrock_handler.setLevel(logging.DEBUG)
        bedrock_handler.setFormatter(file_formatter)
        bedrock_logger = logging.getLogger('src.bedrock_service')
        bedrock_logger.addHandler(bedrock_handler)
        
        # Separate file for quality assessment
        quality_handler = logging.FileHandler(
            LOGS_DIR / f"quality_{today}.log",
            encoding='utf-8'
        )
        quality_handler.setLevel(logging.DEBUG)
        quality_handler.setFormatter(file_formatter)
        quality_logger = logging.getLogger('src.quality')
        quality_logger.addHandler(quality_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('kafka').setLevel(logging.WARNING)
    
    logging.info("=" * 80)
    logging.info("🚀 IMAGE ENHANCEMENT PIPELINE - LOGGING INITIALIZED")
    logging.info("=" * 80)
    logging.info(f"   Level: {level}")
    logging.info(f"   Console output: {log_to_console}")
    logging.info(f"   File output: {log_to_file}")
    if log_to_file:
        logging.info(f"   Log directory: {LOGS_DIR}")
        logging.info(f"   Main log: app_{datetime.now().strftime('%Y-%m-%d')}.log")
        logging.info(f"   Error log: errors_{datetime.now().strftime('%Y-%m-%d')}.log")
        logging.info(f"   Bedrock log: bedrock_{datetime.now().strftime('%Y-%m-%d')}.log")
        logging.info(f"   Quality log: quality_{datetime.now().strftime('%Y-%m-%d')}.log")
    logging.info("=" * 80)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


# Request tracking utilities
class RequestLogger:
    """Helper class for logging request details with structured output"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.request_id: Optional[str] = None
        self.start_time: Optional[float] = None
    
    def start_request(self, request_id: str, operation: str, **kwargs):
        """Log the start of a request"""
        import time
        self.request_id = request_id
        self.start_time = time.time()
        
        self.logger.info("=" * 80)
        self.logger.info(f"📥 REQUEST START | ID: {request_id}")
        self.logger.info(f"   Operation: {operation}")
        for key, value in kwargs.items():
            self.logger.info(f"   {key}: {value}")
        self.logger.info("-" * 80)
    
    def log_routing_decision(self, operation: str, use_ai: bool, reason: str, metrics: dict):
        """Log routing decision (LOCAL vs AI)"""
        method = "☁️ AI (Bedrock)" if use_ai else "💻 LOCAL (OpenCV/PIL)"
        self.logger.info(f"🔀 ROUTING DECISION | {operation}")
        self.logger.info(f"   Decision: {method}")
        self.logger.info(f"   Reason: {reason}")
        self.logger.info(f"   Metrics:")
        for key, value in metrics.items():
            if isinstance(value, float):
                self.logger.info(f"      {key}: {value:.2f}")
            else:
                self.logger.info(f"      {key}: {value}")
    
    def log_threshold_check(self, metric: str, value: float, threshold: float, comparison: str, result: bool):
        """Log threshold comparison"""
        status = "✅ PASS" if result else "❌ FAIL"
        self.logger.info(f"📊 THRESHOLD | {metric}")
        self.logger.info(f"   Value: {value:.2f} {comparison} {threshold:.2f} → {status}")
    
    def log_model_call(self, model_id: str, operation: str, estimated_cost: float):
        """Log AI model invocation"""
        self.logger.info(f"🤖 MODEL CALL")
        self.logger.info(f"   Model: {model_id}")
        self.logger.info(f"   Operation: {operation}")
        self.logger.info(f"   Estimated cost: ${estimated_cost:.4f}")
    
    def log_local_processing(self, operation: str, method: str, details: dict = None):
        """Log local processing step"""
        self.logger.info(f"💻 LOCAL PROCESSING | {operation}")
        self.logger.info(f"   Method: {method}")
        if details:
            for key, value in details.items():
                self.logger.info(f"   {key}: {value}")
    
    def log_quality_metrics(self, metrics: dict):
        """Log quality assessment metrics"""
        self.logger.info(f"📊 QUALITY METRICS")
        for key, value in metrics.items():
            if isinstance(value, float):
                self.logger.info(f"   {key}: {value:.2f}")
            else:
                self.logger.info(f"   {key}: {value}")
    
    def end_request(self, success: bool, **kwargs):
        """Log the end of a request"""
        import time
        
        duration_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
        status = "✅ SUCCESS" if success else "❌ FAILED"
        
        self.logger.info("-" * 80)
        self.logger.info(f"📤 REQUEST END | ID: {self.request_id}")
        self.logger.info(f"   Status: {status}")
        self.logger.info(f"   Duration: {duration_ms}ms")
        for key, value in kwargs.items():
            if isinstance(value, float):
                self.logger.info(f"   {key}: {value:.4f}")
            else:
                self.logger.info(f"   {key}: {value}")
        self.logger.info("=" * 80)


def create_request_logger(name: str) -> RequestLogger:
    """Create a RequestLogger instance"""
    return RequestLogger(get_logger(name))
