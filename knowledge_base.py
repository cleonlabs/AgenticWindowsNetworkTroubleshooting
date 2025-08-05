"""
Knowledge base module for the Windows Network Troubleshooting Agent.
"""
import json
import os
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import openai
from pydantic import BaseModel


class PowerShellCommand(BaseModel):
    """Model representing a PowerShell command in the knowledge base."""
    cmdlet: str
    description: str
    parameters: List[str]
    embedding: Optional[List[float]] = None


class KnowledgeBase:
    """
    Knowledge base for PowerShell network troubleshooting commands.
    Uses embeddings to find relevant commands for natural language queries.
    """
    
    def __init__(self, kb_path: str = None):
        """
        Initialize the knowledge base.
        
        Args:
            kb_path: Path to the knowledge base JSON file. If None, uses the default KB.
        """
        self.commands: List[PowerShellCommand] = []
        self.embeddings = None
        self.loaded = False
        
        # Load the knowledge base
        if kb_path and os.path.exists(kb_path):
            self.load_from_file(kb_path)
        else:
            self.load_default_kb()
    
    def load_default_kb(self):
        """Load the default knowledge base from Guide.md."""
        default_kb = [
            {
                "cmdlet": "Get-NetIPAddress",
                "description": "Gets the IP address configuration (IPv4 and IPv6) and associated interfaces.",
                "parameters": ["InterfaceAlias", "InterfaceIndex", "AddressFamily"]
            },
            {
                "cmdlet": "Get-NetIPConfiguration",
                "description": "Displays IP configuration details including DNS servers, gateways and adapter info.",
                "parameters": ["InterfaceAlias", "Detailed"]
            },
            {
                "cmdlet": "Get-NetAdapter",
                "description": "Shows the network adapter's name, status, MAC address, link speed and related info.",
                "parameters": ["Name", "InterfaceDescription"]
            },
            {
                "cmdlet": "Enable-NetAdapter",
                "description": "Enables (brings up) a network adapter.",
                "parameters": ["Name"]
            },
            {
                "cmdlet": "Disable-NetAdapter",
                "description": "Disables (brings down) a network adapter.",
                "parameters": ["Name"]
            },
            {
                "cmdlet": "Get-NetRoute",
                "description": "Lists entries from the IP routing table (destination prefixes, next hops, metrics).",
                "parameters": ["InterfaceIndex", "DestinationPrefix", "NextHop"]
            },
            {
                "cmdlet": "Test-Connection",
                "description": "Performs an ICMP \"ping\" test to one or more remote hosts.",
                "parameters": ["TargetName", "Count", "Delay", "MaxHops", "BufferSize"]
            },
            {
                "cmdlet": "Test-NetConnection",
                "description": "Tests connectivity over TCP, DNS resolution, traceroute diagnostics.",
                "parameters": ["ComputerName", "Port", "TraceRoute"]
            },
            {
                "cmdlet": "Get-NetTCPConnection",
                "description": "Retrieves active TCP connections (local/remote addresses, ports, state).",
                "parameters": ["LocalPort", "RemoteAddress", "State"]
            },
            {
                "cmdlet": "Resolve-DnsName",
                "description": "Resolves DNS names to IP addresses (nslookup-like functionality).",
                "parameters": ["Server"]
            },
            {
                "cmdlet": "Get-DnsClient",
                "description": "Displays the status of the local DNS client (by network interface).",
                "parameters": ["InterfaceAlias", "InterfaceIndex"]
            },
            {
                "cmdlet": "Get-DnsClientCache",
                "description": "Shows the DNS resolver cache.",
                "parameters": []
            },
            {
                "cmdlet": "Clear-DnsClientCache",
                "description": "Clears the local DNS resolver cache.",
                "parameters": []
            },
            {
                "cmdlet": "Get-DnsClientServerAddress",
                "description": "Lists configured DNS server addresses per interface.",
                "parameters": ["InterfaceAlias"]
            },
            {
                "cmdlet": "Get-Service",
                "description": "Checks status of specified Windows service(s).",
                "parameters": ["Name", "DisplayName"]
            },
            {
                "cmdlet": "Restart-Service",
                "description": "Restarts the specified Windows service.",
                "parameters": ["Name"]
            }
        ]
        
        for cmd in default_kb:
            self.commands.append(PowerShellCommand(**cmd))
        self.loaded = True
    
    def load_from_file(self, file_path: str):
        """
        Load the knowledge base from a JSON file.
        
        Args:
            file_path: Path to the JSON file containing the knowledge base.
        """
        try:
            with open(file_path, 'r') as f:
                kb_data = json.load(f)
            
            for cmd in kb_data:
                self.commands.append(PowerShellCommand(**cmd))
            self.loaded = True
        except Exception as e:
            print(f"Error loading knowledge base: {e}")
            self.load_default_kb()
    
    def save_to_file(self, file_path: str):
        """
        Save the knowledge base to a JSON file.
        
        Args:
            file_path: Path to save the knowledge base JSON.
        """
        kb_data = [cmd.model_dump(exclude={"embedding"}) for cmd in self.commands]
        with open(file_path, 'w') as f:
            json.dump(kb_data, f, indent=2)
    
    async def generate_embeddings(self, client):
        """
        Generate embeddings for all commands in the knowledge base.
        
        Args:
            client: OpenAI client for generating embeddings.
        """
        if not self.commands:
            return
        
        texts = []
        for cmd in self.commands:
            # Combine cmdlet name, description and parameters for richer embedding context
            text = f"{cmd.cmdlet}: {cmd.description} Parameters: {', '.join(cmd.parameters)}"
            texts.append(text)
        
        try:
            response = await client.embeddings.create(
                input=texts,
                model="text-embedding-3-small"  # Or another appropriate model
            )
            
            for i, cmd in enumerate(self.commands):
                cmd.embedding = response.data[i].embedding
            
            # Store embeddings as numpy array for faster similarity search
            self.embeddings = np.array([cmd.embedding for cmd in self.commands])
        except Exception as e:
            print(f"Error generating embeddings: {e}")
    
    def find_relevant_commands(self, query: str, client, top_n: int = 3) -> List[PowerShellCommand]:
        """
        Find commands relevant to the query using embedding similarity.
        
        Args:
            query: The natural language query about a network issue.
            client: OpenAI client for generating embeddings.
            top_n: Number of most relevant commands to return.
            
        Returns:
            List of the most relevant PowerShell commands.
        """
        import numpy as np
        
        if self.embeddings is None:
            # If embeddings aren't generated yet, return some basic commands
            return self.commands[:min(top_n, len(self.commands))]
        
        try:
            # Generate embedding for the query
            query_response = client.embeddings.create(
                input=[query],
                model="text-embedding-3-small"  # Or another appropriate model
            )
            query_embedding = np.array(query_response.data[0].embedding)
            
            # Calculate cosine similarity
            similarities = np.dot(self.embeddings, query_embedding) / (
                np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
            )
            
            # Get indices of top N most similar commands
            top_indices = np.argsort(similarities)[-top_n:][::-1]
            
            # Return the most similar commands
            return [self.commands[i] for i in top_indices]
        except Exception as e:
            print(f"Error finding relevant commands: {e}")
            # Fallback to returning some commands
            return self.commands[:min(top_n, len(self.commands))]
    
    def get_command_by_name(self, cmdlet_name: str) -> Optional[PowerShellCommand]:
        """
        Get a command by its cmdlet name.
        
        Args:
            cmdlet_name: Name of the cmdlet to find.
            
        Returns:
            The PowerShell command if found, None otherwise.
        """
        for cmd in self.commands:
            if cmd.cmdlet.lower() == cmdlet_name.lower():
                return cmd
        return None
    
    def is_valid_command(self, cmdlet_name: str) -> bool:
        """
        Check if a command is valid and exists in the knowledge base.
        
        Args:
            cmdlet_name: Name of the cmdlet to check.
            
        Returns:
            True if the command is in the knowledge base, False otherwise.
        """
        return self.get_command_by_name(cmdlet_name) is not None
