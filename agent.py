"""
Main agent module for the Windows Network Troubleshooting Agent.
"""
import os
import asyncio
import openai
from typing import List, Dict, Any, Optional, Tuple
import json
import re
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from knowledge_base import KnowledgeBase, PowerShellCommand
from powershell_runner import PowerShellRunner
from guardrails import Guardrails

# Load environment variables
load_dotenv()

# Configure OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not found in environment variables.")
    print("Please set your API key in a .env file.")

# Initialize OpenAI client
client = openai.Client(api_key=OPENAI_API_KEY)


class NetworkTroubleshootingAgent:
    """
    Agent for troubleshooting Windows network issues.
    Uses natural language understanding and a knowledge base of PowerShell commands.
    """
    
    def __init__(self):
        """Initialize the network troubleshooting agent."""
        self.kb = KnowledgeBase()
        self.guardrails = Guardrails(self.kb)
        self.ps_runner = PowerShellRunner(self.kb)
        self.conversation_history = []
    
    async def initialize(self):
        """Initialize the agent asynchronously."""
        if OPENAI_API_KEY:
            await self.kb.generate_embeddings(client)
    
    def add_to_history(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.conversation_history.append({"role": role, "content": content})
        # Keep only the last 10 messages to avoid token limits
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def analyze_issue(self, user_query: str) -> Dict:
        """
        Analyze a network issue described in natural language.
        
        Args:
            user_query: Natural language description of the network issue.
            
        Returns:
            Dictionary with analysis results and recommended PowerShell commands.
        """
        # Add user query to conversation history
        self.add_to_history("user", user_query)
        
        # Find relevant commands
        relevant_commands = self.kb.find_relevant_commands(user_query, client)
        
        # Format commands for context
        commands_context = []
        for cmd in relevant_commands:
            param_str = ", ".join([f"-{p}" for p in cmd.parameters]) if cmd.parameters else ""
            commands_context.append(f"{cmd.cmdlet} {param_str}: {cmd.description}")
        
        # Prepare system message with instructions and available commands
        system_message = {
            "role": "system",
            "content": f"""You are a Windows network troubleshooting assistant.
Your task is to analyze the user's network issue and suggest appropriate PowerShell commands to diagnose and fix the problem.
You have the following PowerShell commands available:

{chr(10).join(commands_context)}

For each command you recommend:
1. Explain why this command is relevant to the user's issue
2. Show the exact command syntax they should run
3. Explain what output to expect and how to interpret it

Only recommend commands from the list provided. Do not make up commands.
Provide specific command lines, not general advice."""
        }
        
        # Get response from LLM
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[system_message] + self.conversation_history,
                temperature=0.3,
                max_tokens=1000
            )
            
            assistant_message = response.choices[0].message.content
            self.add_to_history("assistant", assistant_message)
            
            # Extract PowerShell commands from the response
            commands = self.extract_commands(assistant_message)
            
            # Validate each command
            validated_commands = []
            for cmd in commands:
                is_valid, reason = self.ps_runner.validate_command(cmd)
                validated_commands.append({
                    "command": cmd,
                    "valid": is_valid,
                    "reason": reason
                })
            
            return {
                "analysis": assistant_message,
                "commands": validated_commands
            }
            
        except Exception as e:
            return {
                "error": f"Error analyzing issue: {str(e)}",
                "commands": []
            }
    
    def extract_commands(self, text: str) -> List[str]:
        """
        Extract PowerShell commands from text.
        
        Args:
            text: Text containing PowerShell commands.
            
        Returns:
            List of extracted commands.
        """
        # Look for commands in code blocks
        code_block_pattern = r"```(?:powershell)?\s*([\s\S]*?)```"
        code_blocks = re.findall(code_block_pattern, text)
        
        # Look for commands in inline code
        inline_code_pattern = r"`(.*?)`"
        inline_codes = re.findall(inline_code_pattern, text)
        
        # Combine and filter the results
        all_potential_commands = code_blocks + inline_codes
        
        # Filter to include only strings that contain PowerShell cmdlets
        commands = []
        for cmd in all_potential_commands:
            cmd = cmd.strip()
            if cmd and any(cmdlet.lower() in cmd.lower() for cmdlet in ['get-net', 'test-', 'resolve-dns', 'get-dns', 'clear-dns', 'restart-service', 'get-service']):
                commands.append(cmd)
        
        return commands
    
    async def execute_command(self, command: str) -> Dict:
        """
        Execute a PowerShell command.
        
        Args:
            command: The PowerShell command to execute.
            
        Returns:
            Dictionary with execution results.
        """
        # Use guardrails to validate the command
        is_valid, reason = self.guardrails.validate_command(command)
        self.guardrails.log_validation('command', command, is_valid, reason)
        
        if not is_valid:
            return {
                "command": command,
                "executed": False,
                "error": reason,
                "reason": reason,
                "valid": False
            }
        
        # Run the command
        result = self.ps_runner.run_command(command)
        
        # Add the results to conversation history
        if result["executed"]:
            # Sanitize output to remove sensitive information
            output = result.get("output", "") or result.get("error", "No output")
            sanitized_output = self.guardrails.sanitize_output(output)
            
            self.add_to_history("system", f"Command executed: `{command}`\nOutput:\n```\n{sanitized_output}\n```")
            
            # Get interpretation of results
            interpretation = await self.interpret_results(command, sanitized_output)
            self.add_to_history("assistant", interpretation)
            
            result["interpretation"] = interpretation
            result["output"] = sanitized_output
        
        return result
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def interpret_results(self, command: str, output: str) -> str:
        """
        Interpret the results of a PowerShell command.
        
        Args:
            command: The PowerShell command that was executed.
            output: The output from the command.
            
        Returns:
            String with interpretation of the results.
        """
        try:
            # Get LLM to interpret the command output
            system_message = {
                "role": "system",
                "content": """You are a Windows network troubleshooting assistant.
Your task is to interpret the output of a PowerShell command and explain what it means for the user's network issue.
Focus on:
1. Explaining what the output shows in simple terms
2. Identifying any potential issues or anomalies
3. Suggesting next steps based on this information
Be concise but thorough in your explanation."""
            }
            
            messages = [
                system_message,
                {"role": "user", "content": f"I ran this PowerShell command: `{command}`\n\nHere's the output:\n```\n{output}\n```\n\nPlease explain what this means and what I should do next."}
            ]
            
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.3,
                max_tokens=800
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error interpreting results: {str(e)}"
    
    def is_network_related_query(self, query: str) -> Tuple[bool, str]:
        """
        Check if a query is related to network troubleshooting.
        
        Args:
            query: The user's query.
            
        Returns:
            Tuple of (is_related, explanation)
        """
        # Use guardrails to validate input
        is_valid, reason = self.guardrails.validate_user_input(query)
        self.guardrails.log_validation('user_query', query, is_valid, reason)
        return is_valid, reason
