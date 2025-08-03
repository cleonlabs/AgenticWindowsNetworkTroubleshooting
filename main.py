"""
Main CLI application for the Windows Network Troubleshooting Agent.
"""
import asyncio
import os
import sys
import textwrap
from colorama import init, Fore, Style

from agent import NetworkTroubleshootingAgent

# Initialize colorama for cross-platform colored terminal output
init()


class CLI:
    """Command-line interface for the Network Troubleshooting Agent."""
    
    def __init__(self):
        """Initialize the CLI."""
        self.agent = NetworkTroubleshootingAgent()
    
    def print_banner(self):
        """Print the application banner."""
        banner = """
        ╭───────────────────────────────────────────────╮
        │                                               │
        │   Windows Network Troubleshooting Agent       │
        │                                               │
        ╰───────────────────────────────────────────────╯
        """
        print(Fore.CYAN + banner + Style.RESET_ALL)
        print(Fore.WHITE + "Describe your network issue, and I'll help diagnose it." + Style.RESET_ALL)
        print(Fore.YELLOW + "Type 'exit' to quit." + Style.RESET_ALL)
        print()
    
    def print_with_formatting(self, text, width=80):
        """Print text with proper formatting and color coding."""
        # Format code blocks with special coloring
        in_code_block = False
        for line in text.split('\n'):
            if line.strip() == '```' or line.strip() == '```powershell':
                in_code_block = not in_code_block
                print(Fore.CYAN + line + Style.RESET_ALL)
            elif in_code_block:
                print(Fore.GREEN + line + Style.RESET_ALL)
            else:
                # Format regular text with wrapping
                wrapped_lines = textwrap.fill(line, width=width) if line.strip() else line
                print(Fore.WHITE + wrapped_lines + Style.RESET_ALL)
    
    async def run(self):
        """Run the CLI application."""
        # Initialize agent
        print(Fore.YELLOW + "Initializing agent..." + Style.RESET_ALL)
        await self.agent.initialize()
        
        # Print banner
        self.print_banner()
        
        # Main loop
        while True:
            try:
                # Get user input
                user_input = input(Fore.CYAN + "\nWhat network issue are you experiencing? " + Style.RESET_ALL)
                print()
                
                # Check for exit command
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print(Fore.YELLOW + "Goodbye!" + Style.RESET_ALL)
                    break
                
                # Check if query is network-related
                is_network_related, reason = self.agent.is_network_related_query(user_input)
                if not is_network_related:
                    print(Fore.RED + "Sorry, I can only help with network-related issues." + Style.RESET_ALL)
                    print(Fore.YELLOW + "Please try again with a network-related question." + Style.RESET_ALL)
                    continue
                
                # Analyze the issue
                print(Fore.YELLOW + "Analyzing your issue..." + Style.RESET_ALL)
                analysis_result = await self.agent.analyze_issue(user_input)
                
                if "error" in analysis_result:
                    print(Fore.RED + analysis_result["error"] + Style.RESET_ALL)
                    continue
                
                # Print the analysis
                print(Fore.GREEN + "Analysis:" + Style.RESET_ALL)
                self.print_with_formatting(analysis_result["analysis"])
                print()
                
                # If there are valid commands to run
                valid_commands = [cmd for cmd in analysis_result["commands"] if cmd["valid"]]
                if valid_commands:
                    print(Fore.GREEN + f"I can run {len(valid_commands)} PowerShell command(s) to help diagnose this issue:" + Style.RESET_ALL)
                    
                    for i, cmd in enumerate(valid_commands, 1):
                        print(f"{i}. {Fore.CYAN}{cmd['command']}{Style.RESET_ALL}")
                    
                    # Ask for permission
                    print()
                    permission = input(Fore.YELLOW + "May I run diagnostic commands? (Y/N): " + Style.RESET_ALL)
                    
                    if permission.lower() == 'y':
                        for cmd in valid_commands:
                            print(Fore.YELLOW + f"\nRunning: {cmd['command']}" + Style.RESET_ALL)
                            result = await self.agent.execute_command(cmd['command'])
                            
                            if result["executed"]:
                                print(Fore.GREEN + "Command executed successfully!" + Style.RESET_ALL)
                                if result.get("output"):
                                    print(Fore.WHITE + "Output:" + Style.RESET_ALL)
                                    print(Fore.CYAN + "```" + Style.RESET_ALL)
                                    print(Fore.GREEN + result["output"] + Style.RESET_ALL)
                                    print(Fore.CYAN + "```" + Style.RESET_ALL)
                                
                                if result.get("error"):
                                    print(Fore.RED + "Error:" + Style.RESET_ALL)
                                    print(result["error"])
                                
                                # Print interpretation
                                if result.get("interpretation"):
                                    print(Fore.WHITE + "\nInterpretation:" + Style.RESET_ALL)
                                    self.print_with_formatting(result["interpretation"])
                            else:
                                print(Fore.RED + f"Failed to execute command: {result.get('reason', 'Unknown error')}" + Style.RESET_ALL)
                    else:
                        print(Fore.YELLOW + "Commands not executed. Let me know if you want to try something else." + Style.RESET_ALL)
                else:
                    print(Fore.YELLOW + "No valid PowerShell commands found to run for this issue." + Style.RESET_ALL)
                    
                    if analysis_result["commands"]:
                        print(Fore.RED + "Invalid commands:" + Style.RESET_ALL)
                        for cmd in analysis_result["commands"]:
                            print(f"- {cmd['command']}: {cmd['reason']}")
            
            except KeyboardInterrupt:
                print(Fore.YELLOW + "\nOperation cancelled. Type 'exit' to quit." + Style.RESET_ALL)
            except Exception as e:
                print(Fore.RED + f"\nError: {str(e)}" + Style.RESET_ALL)


async def main():
    """Main entry point for the application."""
    cli = CLI()
    await cli.run()


if __name__ == "__main__":
    try:
        if os.name != 'nt':
            print(Fore.YELLOW + "Warning: This tool is designed for Windows systems.")
            print("Some functionality may not work on non-Windows systems." + Style.RESET_ALL)
        
        asyncio.run(main())
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nApplication terminated." + Style.RESET_ALL)
        sys.exit(0)
