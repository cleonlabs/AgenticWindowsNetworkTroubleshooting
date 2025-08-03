# Windows Network Troubleshooting Agent

An AI-powered agent that helps troubleshoot Windows network issues using PowerShell commands.

## Overview

This agent interprets natural language descriptions of network issues, matches them to relevant PowerShell commands from its knowledge base, and helps diagnose and resolve Windows network problems.

## Features

- Natural language interpretation of network issues
- Knowledge base of PowerShell network diagnostic commands
- Safe execution of PowerShell commands with user permission
- Logging of all command executions
- Security guardrails to prevent unsafe operations

## Setup

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your-api-key-here
   ```
4. Run the agent:
   ```
   python main.py
   ```

## Usage

1. Describe your network issue in plain language
2. The agent will suggest PowerShell commands to diagnose the issue
3. Approve or deny running the suggested commands
4. View the results and follow the agent's guidance

## Safety

The agent implements several safety measures:
- Asks for permission before executing any command
- Only executes commands from its pre-approved knowledge base
- Validates that commands are related to network troubleshooting
- Checks for potentially risky patterns
- Logs all command executions with timestamps

## Architecture

- LLM Orchestrator: OpenAI-based agent logic
- Knowledge Store: Vector database of PowerShell commands
- PowerShell Runner: Safe execution of commands
- Guardrails: Input and output validation
- CLI Interface: Terminal-based user interaction
