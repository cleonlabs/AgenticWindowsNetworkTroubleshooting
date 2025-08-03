"""
Guardrails module for ensuring safe operation of the Windows Network Troubleshooting Agent.
"""
import re
import logging
from typing import Dict, List, Tuple, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("guardrails.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("guardrails")

# Network-related keywords for input validation
NETWORK_KEYWORDS = [
    'network', 'internet', 'wifi', 'wi-fi', 'ethernet', 'connection', 
    'connect', 'ping', 'dns', 'ip', 'tcp', 'udp', 'router', 'gateway',
    'subnet', 'adapter', 'interface', 'dhcp', 'http', 'https', 'ftp',
    'vpn', 'proxy', 'firewall', 'latency', 'packet', 'speed', 'bandwidth',
    'wireless', 'wired', 'offline', 'online', 'disconnect'
]

# Patterns that indicate potential harmful operations
HARMFUL_PATTERNS = [
    r'shutdown', r'restart', r'reboot',           # System reboot operations
    r'format', r'delete', r'remove', r'uninstall', # Deletion operations
    r'password', r'credential', r'secret',        # Sensitive data
    r'encrypt', r'decrypt', r'crack',             # Security operations
    r'hack', r'exploit', r'vulnerability',        # Malicious intent
    r'malware', r'virus', r'trojan',              # Harmful software
    r'rm\s+[\-rf]', r'del', r'rd', r'rmdir',      # Deletion commands
    r'invoke-expression', r'iex',                 # Execution commands
    r'new-item', r'set-',                         # Creation/modification
    r'start-process'                              # Process creation
]

# Safe PowerShell cmdlet prefixes for network diagnostics
SAFE_CMDLET_PREFIXES = [
    'get-net', 'test-', 'resolve-dns', 'get-dns', 
    'clear-dnsclient', 'get-service', 'restart-service'
]


class Guardrails:
    """
    Implements safety guardrails for the Windows Network Troubleshooting Agent.
    """
    
    def __init__(self, kb_manager):
        """
        Initialize the guardrails.
        
        Args:
            kb_manager: Knowledge base manager for command validation.
        """
        self.kb_manager = kb_manager
    
    def validate_user_input(self, user_input: str) -> Tuple[bool, str]:
        """
        Validate that user input is related to network issues and safe.
        
        Args:
            user_input: The user's input to validate.
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check if input is too long
        if len(user_input) > 1000:
            return False, "Input is too long (>1000 characters)"
        
        # Check if input is related to network troubleshooting
        if not self.is_network_related(user_input):
            return False, "Input doesn't appear to be related to network troubleshooting"
        
        # Check for harmful patterns
        for pattern in HARMFUL_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                return False, f"Input contains potentially harmful pattern: {pattern}"
        
        return True, "Input is valid"
    
    def is_network_related(self, text: str) -> bool:
        """
        Check if text is related to network troubleshooting.
        
        Args:
            text: Text to check.
            
        Returns:
            True if text is related to network troubleshooting, False otherwise.
        """
        lower_text = text.lower()
        return any(keyword in lower_text for keyword in NETWORK_KEYWORDS)
    
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
        
        # Check for harmful patterns
        for pattern in HARMFUL_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Command contains harmful pattern: {pattern}"
        
        # Extract the base command (the cmdlet name)
        cmdlet_match = re.match(r'^(\S+)', command.strip())
        if not cmdlet_match:
            return False, "Could not parse command"
        
        cmdlet_name = cmdlet_match.group(1)
        
        # Check if command is in the knowledge base
        if not self.kb_manager.is_valid_command(cmdlet_name):
            return False, f"Command '{cmdlet_name}' not found in knowledge base"
        
        # Check if command starts with a safe prefix
        if not any(cmdlet_name.lower().startswith(prefix) for prefix in SAFE_CMDLET_PREFIXES):
            return False, f"Command '{cmdlet_name}' is not a safe network diagnostic command"
        
        # Validate parameters against knowledge base
        command_obj = self.kb_manager.get_command_by_name(cmdlet_name)
        if command_obj:
            valid_params = command_obj.parameters
            
            # Extract parameters from command
            param_pattern = r'-(\w+)'
            params_in_command = re.findall(param_pattern, command)
            
            # Check if all parameters are valid
            for param in params_in_command:
                if param not in valid_params:
                    return False, f"Parameter '{param}' is not valid for command '{cmdlet_name}'"
        
        return True, "Command is valid"
    
    def sanitize_output(self, output: str) -> str:
        """
        Sanitize command output to remove potentially sensitive information.
        
        Args:
            output: Command output to sanitize.
            
        Returns:
            Sanitized output.
        """
        # Patterns to identify potentially sensitive info
        sensitive_patterns = [
            # MAC addresses
            (r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', '[MAC_ADDRESS]'),
            
            # IPv4 addresses (simple pattern)
            (r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', '[IP_ADDRESS]'),
            
            # Password fields
            (r'(?i)password\s*[:=]\s*\S+', 'password: [REDACTED]'),
            
            # Authentication tokens/keys
            (r'(?i)(api[-_]?key|token|secret)[:=]\s*\S+', '[CREDENTIALS_REDACTED]'),
            
            # Username with domain
            (r'(?i)username\s*[:=]\s*\S+\\+\S+', 'username: [REDACTED]')
        ]
        
        sanitized = output
        for pattern, replacement in sensitive_patterns:
            sanitized = re.sub(pattern, replacement, sanitized)
        
        return sanitized
    
    def log_validation(self, input_type: str, content: str, is_valid: bool, reason: str):
        """
        Log validation results for auditing.
        
        Args:
            input_type: Type of input being validated (e.g., 'user_query', 'command').
            content: The content being validated.
            is_valid: Whether the content is valid.
            reason: Reason for validation result.
        """
        logger.info(
            f"Validation - Type: {input_type}, Valid: {is_valid}, Reason: {reason}, "
            f"Content: {content[:50]}{'...' if len(content) > 50 else ''}"
        )
