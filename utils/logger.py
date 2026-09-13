"""
Logging utility for the application
"""

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional, Dict, Any
import json

# Log levels
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        log_message = super().format(record)
        if hasattr(record, 'levelname'):
            color = self.COLORS.get(record.levelname, '')
            reset = self.COLORS['RESET']
            return f"{color}{log_message}{reset}"
        return log_message

def setup_logger(name: str, log_file: str, level=logging.INFO, console=True) -> logging.Logger:
    """Setup a logger with file and console handlers"""
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    simple_formatter = ColoredFormatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)
    
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(simple_formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    
    return logger

class LoggerMixin:
    """Mixin class to add logging capability"""
    
    @property
    def logger(self) -> logging.Logger:
        name = '.'.join([__name__, self.__class__.__name__])
        return logging.getLogger(name)
    
    def log_exception(self, e: Exception, message: str = "Exception occurred"):
        """Log an exception with traceback"""
        self.logger.error(f"{message}: {str(e)}")
        self.logger.debug(traceback.format_exc())

class PerformanceLogger:
    """Log performance metrics"""
    
    def __init__(self, logger: logging.Logger, interval: int = 60):
        self.logger = logger
        self.interval = interval
        self.metrics: Dict[str, list] = {}
        self.start_time = datetime.now()
        self.last_log_time = datetime.now()
    
    def log_metric(self, name: str, value: float):
        """Log a metric"""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)
        
        if len(self.metrics[name]) > 100:
            self.metrics[name].pop(0)
        
        now = datetime.now()
        if (now - self.last_log_time).total_seconds() >= self.interval:
            self.log_summary()
            self.last_log_time = now
    
    def get_average(self, name: str) -> float:
        if name in self.metrics and self.metrics[name]:
            return sum(self.metrics[name]) / len(self.metrics[name])
        return 0.0
    
    def log_summary(self):
        self.logger.info("=" * 50)
        self.logger.info("📊 Performance Summary")
        self.logger.info("=" * 50)
        
        for name, values in self.metrics.items():
            if values:
                avg = sum(values) / len(values)
                self.logger.info(f"   {name}: avg={avg:.2f}")
        
        uptime = (datetime.now() - self.start_time).total_seconds()
        self.logger.info(f"   Uptime: {uptime:.1f} seconds")
        self.logger.info("=" * 50)

class AlertLogger:
    """Special logger for alerts"""
    
    def __init__(self, log_file: str = 'logs/alerts.log'):
        self.logger = setup_logger('alerts', log_file, console=False)
    
    def log_alert(self, alert_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = datetime.now().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'type': alert_type,
            'details': details
        }
        self.logger.warning(f"ALERT: {alert_type} - {details}")
        return log_entry
    
    def log_drowsy_alert(self, ear_value: float, duration: int, **kwargs) -> Dict[str, Any]:
        return self.log_alert('drowsiness', {
            'ear': ear_value,
            'duration': duration,
            **kwargs
        })
    
    def log_yawn_alert(self, mar_value: float, **kwargs) -> Dict[str, Any]:
        return self.log_alert('yawn', {'mar': mar_value, **kwargs})