"""
PowerShell runner module for safely executing Windows PowerShell commands.
"""
import subprocess
import os
import re
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("powershell_commands.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("powershell_runner")

# List of disallowed command patterns
DISALLOWED_PATTERNS = [
    r'rm\s+-r', r'rmdir', r'del\s+', r'remove-item',  # Destructive file operations
    r'shutdown', r'restart-computer',  # System shutdown/restart
    r'remove-', r'uninstall-',  # Remove/uninstall operations
    r'invoke-expression', r'iex',  # Command injection risk
    r'invoke-webrequest', r'wget', r'curl',  # Web requests
    r'new-item', r'set-',  # File creation or setting values
    r'start-process',  # Process creation
    r'out-file', r'>>', r'>', r'\|'  # File output redirection
]


class PowerShellRunner:
    """
    Safely runs PowerShell commands for network troubleshooting.
    Includes validation, logging, and security checks.
    """
    
    def __init__(self, kb_manager):
        """
        Initialize the PowerShell runner.
        
        Args:
            kb_manager: Knowledge base manager for command validation.
        """
        self.kb_manager = kb_manager
        self.log_file = "powershell_commands.log"
        
    def validate_command(self, command: str) -> Tuple[bool, str]:
        """
        Validate that a PowerShell command is safe to execute.
        
        Args:
            command: The PowerShell command to validate.
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check if command is too long
        if len(command) > 500:
            return False, "Command is too long (>500 characters)"
        
        # Check for disallowed patterns
        for pattern in DISALLOWED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Command contains disallowed pattern: {pattern}"
        
        # Extract the base command (the cmdlet name)
        cmdlet_match = re.match(r'^(\S+)', command.strip())
        if not cmdlet_match:
            return False, "Could not parse command"
        
        cmdlet_name = cmdlet_match.group(1)
        
        # Check if command is in the knowledge base
        if not self.kb_manager.is_valid_command(cmdlet_name):
            return False, f"Command '{cmdlet_name}' not found in knowledge base"
        
        # Check if command is a network-related command
        if not cmdlet_name.lower().startswith(('get-net', 'test-', 'resolve-dns', 'get-dns', 'clear-dns', 'get-service', 'restart-service')):
            return False, f"Command '{cmdlet_name}' is not a network troubleshooting command"
        
        return True, "Command validated"
    
    def run_command(self, command: str, check_only: bool = False) -> Dict:
        """
        Run a PowerShell command safely.
        
        Args:
            command: The PowerShell command to run.
            check_only: If True, only validate but don't execute the command.
            
        Returns:
            Dictionary with command results or validation info.
        """
        # Validate the command first
        is_valid, reason = self.validate_command(command)
        
        result = {
            "command": command,
            "timestamp": datetime.now().isoformat(),
            "valid": is_valid,
            "reason": reason,
            "output": None,
            "error": None,
            "executed": False
        }
        
        # Log the validation attempt
        logger.info(f"Command validation: {command} - Valid: {is_valid}, Reason: {reason}")
        
        # If invalid or check-only mode, return without executing
        if not is_valid or check_only:
            return result
        
        # Execute the PowerShell command
        try:
            # Use 'pwsh' for PowerShell Core, or 'powershell' for Windows PowerShell
            process = subprocess.run(
                ['pwsh', '-Command', command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            result["executed"] = True
            result["output"] = process.stdout
            result["error"] = process.stderr if process.stderr else None
            result["returncode"] = process.returncode
            
            # Log the execution
            log_entry = (
                f"EXECUTED: {command}\n"
                f"RETURN CODE: {process.returncode}\n"
                f"OUTPUT: {process.stdout}\n"
                f"ERROR: {process.stderr}\n"
                f"{'='*50}\n"
            )
            logger.info(log_entry)
            
        except subprocess.TimeoutExpired:
            result["error"] = "Command execution timed out after 30 seconds"
            logger.error(f"Command timeout: {command}")
            
        except Exception as e:
            result["error"] = f"Error executing command: {str(e)}"
            logger.error(f"Command error: {command} - {str(e)}")
        
        return result
