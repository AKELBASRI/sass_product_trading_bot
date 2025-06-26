#!/usr/bin/env python3
"""
Redis Data Explorer - Explore your existing MT5 data
"""

import redis
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON

class RedisDataExplorer:
    def __init__(self, redis_host='localhost', redis_port=6382):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.console = Console()
    
    def explore_all_keys(self):
        """Explore all keys in Redis"""
        self.console.print("🔍 [bold cyan]Exploring Redis Database[/bold cyan]")
        self.console.print("=" * 50)
        
        try:
            # Get all keys
            all_keys = self.redis_client.keys("*")
            self.console.print(f"📊 Total keys found: [bold green]{len(all_keys)}[/bold green]\n")
            
            # Group keys by prefix
            key_groups = {}
            for key in all_keys:
                prefix = key.split(':')[0] if ':' in key else 'no_prefix'
                if prefix not in key_groups:
                    key_groups[prefix] = []
                key_groups[prefix].append(key)
            
            # Create table for key overview
            table = Table(title="🗂️ Key Groups Overview")
            table.add_column("Prefix", style="cyan", no_wrap=True)
            table.add_column("Count", style="magenta")
            table.add_column("Sample Keys", style="green")
            
            for prefix, keys in key_groups.items():
                sample_keys = ', '.join(keys[:3])
                if len(keys) > 3:
                    sample_keys += f" ... (+{len(keys)-3} more)"
                table.add_row(prefix, str(len(keys)), sample_keys)
            
            self.console.print(table)
            self.console.print()
            
            return key_groups
            
        except Exception as e:
            self.console.print(f"❌ Error exploring keys: {e}")
            return {}
    
    def explore_mt5_data(self):
        """Specifically explore MT5 data"""
        self.console.print("🎯 [bold yellow]MT5 Data Analysis[/bold yellow]")
        self.console.print("=" * 50)
        
        try:
            mt5_keys = self.redis_client.keys("mt5:*")
            
            if not mt5_keys:
                self.console.print("❌ No MT5 keys found")
                return
            
            self.console.print(f"📈 MT5 keys found: [bold green]{len(mt5_keys)}[/bold green]\n")
            
            # Analyze each MT5 key
            for key in sorted(mt5_keys):
                self.analyze_key(key)
                
        except Exception as e:
            self.console.print(f"❌ Error exploring MT5 data: {e}")
    
    def analyze_key(self, key):
        """Analyze a specific key"""
        try:
            # Get key type
            key_type = self.redis_client.type(key)
            
            # Get value based on type
            if key_type == 'string':
                value = self.redis_client.get(key)
                
                # Try to parse as JSON
                try:
                    json_data = json.loads(value)
                    self.display_json_key(key, json_data)
                except json.JSONDecodeError:
                    self.display_string_key(key, value)
                    
            elif key_type == 'list':
                length = self.redis_client.llen(key)
                sample_items = self.redis_client.lrange(key, 0, 2)
                self.display_list_key(key, length, sample_items)
                
            elif key_type == 'set':
                members = self.redis_client.smembers(key)
                self.display_set_key(key, members)
                
            elif key_type == 'hash':
                fields = self.redis_client.hgetall(key)
                self.display_hash_key(key, fields)
                
        except Exception as e:
            self.console.print(f"❌ Error analyzing key {key}: {e}")
    
    def display_json_key(self, key, data):
        """Display JSON key data"""
        # Create a summary of the JSON data
        if isinstance(data, dict):
            summary = f"Dict with {len(data)} fields"
            if 'timestamp' in data:
                try:
                    ts = datetime.fromtimestamp(data['timestamp'])
                    summary += f" | Time: {ts.strftime('%Y-%m-%d %H:%M:%S')}"
                except:
                    pass
        elif isinstance(data, list):
            summary = f"List with {len(data)} items"
        else:
            summary = f"Value: {str(data)[:50]}"
        
        panel = Panel(
            JSON.from_data(data) if len(str(data)) < 500 else f"Large JSON object: {summary}",
            title=f"🔑 {key}",
            border_style="green"
        )
        self.console.print(panel)
    
    def display_string_key(self, key, value):
        """Display string key data"""
        display_value = value[:100] + "..." if len(value) > 100 else value
        panel = Panel(
            display_value,
            title=f"🔑 {key} (string)",
            border_style="blue"
        )
        self.console.print(panel)
    
    def display_list_key(self, key, length, sample_items):
        """Display list key data"""
        content = f"List length: {length}\nSample items:\n"
        for i, item in enumerate(sample_items):
            content += f"  {i}: {item[:50]}{'...' if len(item) > 50 else ''}\n"
        
        panel = Panel(
            content,
            title=f"🔑 {key} (list)",
            border_style="yellow"
        )
        self.console.print(panel)
    
    def display_set_key(self, key, members):
        """Display set key data"""
        content = f"Set members ({len(members)}):\n"
        for member in list(members)[:5]:
            content += f"  • {member}\n"
        if len(members) > 5:
            content += f"  ... and {len(members)-5} more"
        
        panel = Panel(
            content,
            title=f"🔑 {key} (set)",
            border_style="magenta"
        )
        self.console.print(panel)
    
    def display_hash_key(self, key, fields):
        """Display hash key data"""
        content = f"Hash fields ({len(fields)}):\n"
        for field, value in list(fields.items())[:5]:
            display_value = value[:30] + "..." if len(value) > 30 else value
            content += f"  {field}: {display_value}\n"
        if len(fields) > 5:
            content += f"  ... and {len(fields)-5} more fields"
        
        panel = Panel(
            content,
            title=f"🔑 {key} (hash)",
            border_style="cyan"
        )
        self.console.print(panel)
    
    def get_data_freshness(self):
        """Check how fresh the data is"""
        self.console.print("⏰ [bold blue]Data Freshness Check[/bold blue]")
        self.console.print("=" * 50)
        
        try:
            # Check for timestamp-related keys
            timestamp_keys = self.redis_client.keys("*timestamp*") + self.redis_client.keys("*time*")
            
            latest_time = None
            latest_key = None
            
            for key in timestamp_keys:
                try:
                    value = self.redis_client.get(key)
                    if value and value.isdigit():
                        timestamp = int(value)
                        if latest_time is None or timestamp > latest_time:
                            latest_time = timestamp
                            latest_key = key
                except:
                    continue
            
            if latest_time:
                latest_datetime = datetime.fromtimestamp(latest_time)
                time_diff = (datetime.now() - latest_datetime).total_seconds()
                
                self.console.print(f"🕐 Latest timestamp: [green]{latest_datetime.strftime('%Y-%m-%d %H:%M:%S')}[/green]")
                self.console.print(f"🔑 From key: [cyan]{latest_key}[/cyan]")
                self.console.print(f"⏱️ Age: [yellow]{time_diff:.0f} seconds ago[/yellow]")
                
                if time_diff < 60:
                    self.console.print("✅ [green]Data is fresh![/green]")
                elif time_diff < 300:
                    self.console.print("⚠️ [yellow]Data is recent[/yellow]")
                else:
                    self.console.print("❌ [red]Data is stale[/red]")
            else:
                self.console.print("❓ No timestamp data found")
                
        except Exception as e:
            self.console.print(f"❌ Error checking freshness: {e}")
    
    def run_full_exploration(self):
        """Run complete exploration"""
        self.console.clear()
        self.console.print("🚀 [bold green]Redis Data Explorer[/bold green]")
        self.console.print()
        
        # Basic key exploration
        key_groups = self.explore_all_keys()
        
        # MT5 specific exploration
        if 'mt5' in key_groups:
            self.console.print()
            self.explore_mt5_data()
        
        # Data freshness check
        self.console.print()
        self.get_data_freshness()
        
        self.console.print()
        self.console.print("✨ [bold green]Exploration complete![/bold green]")

def main():
    """Main function"""
    explorer = RedisDataExplorer()
    explorer.run_full_exploration()

if __name__ == "__main__":
    main()