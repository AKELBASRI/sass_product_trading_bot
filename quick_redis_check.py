#!/usr/bin/env python3
"""
Fixed Redis Data Check - Handles different data types correctly
"""

import redis
import json
from datetime import datetime

def quick_check():
    print("🔍 Fixed Redis Data Check")
    print("=" * 40)
    
    try:
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6382, decode_responses=True)
        r.ping()
        print("✅ Redis connection successful")
        
        # Get all keys
        all_keys = r.keys("*")
        mt5_keys = [k for k in all_keys if k.startswith("mt5:")]
        
        print(f"\n📊 Database Overview:")
        print(f"   Total keys: {len(all_keys)}")
        print(f"   MT5 keys: {len(mt5_keys)}")
        
        # Show all keys with their types
        print(f"\n🗂️ All Keys:")
        for key in sorted(all_keys):
            key_type = r.type(key)
            print(f"   {key} ({key_type})")
        
        # Handle different key types properly
        if mt5_keys:
            print(f"\n🎯 MT5 Key Details:")
            for key in sorted(mt5_keys):
                try:
                    key_type = r.type(key)
                    print(f"\n   📋 {key} ({key_type}):")
                    
                    if key_type == 'string':
                        value = r.get(key)
                        if value:
                            try:
                                data = json.loads(value)
                                print("     JSON Data:")
                                for k, v in list(data.items())[:5]:
                                    if isinstance(v, (int, float)) and k in ['timestamp', 'time']:
                                        try:
                                            dt = datetime.fromtimestamp(v)
                                            print(f"       {k}: {v} ({dt.strftime('%Y-%m-%d %H:%M:%S')})")
                                        except:
                                            print(f"       {k}: {v}")
                                    else:
                                        print(f"       {k}: {str(v)[:60]}")
                                if len(data) > 5:
                                    print(f"       ... and {len(data)-5} more fields")
                            except json.JSONDecodeError:
                                print(f"     String Value: {value[:100]}")
                    
                    elif key_type == 'hash':
                        hash_data = r.hgetall(key)
                        print("     Hash Fields:")
                        for field, value in list(hash_data.items())[:10]:
                            # Try to parse timestamp fields
                            if field in ['timestamp', 'time', 'last_update'] and value.isdigit():
                                try:
                                    dt = datetime.fromtimestamp(int(value))
                                    print(f"       {field}: {value} ({dt.strftime('%Y-%m-%d %H:%M:%S')})")
                                except:
                                    print(f"       {field}: {value}")
                            else:
                                print(f"       {field}: {str(value)[:60]}")
                        if len(hash_data) > 10:
                            print(f"       ... and {len(hash_data)-10} more fields")
                    
                    elif key_type == 'list':
                        list_length = r.llen(key)
                        sample_items = r.lrange(key, 0, 2)
                        print(f"     List Length: {list_length}")
                        print("     Sample Items:")
                        for i, item in enumerate(sample_items):
                            print(f"       [{i}]: {item[:60]}")
                    
                    elif key_type == 'set':
                        members = r.smembers(key)
                        print(f"     Set Members ({len(members)}):")
                        for member in list(members)[:5]:
                            print(f"       • {member}")
                        if len(members) > 5:
                            print(f"       ... and {len(members)-5} more")
                    
                    elif key_type == 'zset':
                        zset_data = r.zrange(key, 0, 4, withscores=True)
                        print(f"     Sorted Set ({r.zcard(key)} members):")
                        for member, score in zset_data:
                            print(f"       {member}: {score}")
                    
                except Exception as e:
                    print(f"     ❌ Error reading {key}: {e}")
        
        # Memory info
        try:
            info = r.info('memory')
            print(f"\n💾 Memory Usage:")
            print(f"   Used: {info.get('used_memory_human', 'N/A')}")
            print(f"   Peak: {info.get('used_memory_peak_human', 'N/A')}")
            print(f"   Dataset: {info.get('used_memory_dataset', 'N/A')} bytes")
        except Exception as e:
            print(f"   ❌ Memory info error: {e}")
        
        # Database info
        try:
            keyspace_info = r.info('keyspace')
            print(f"\n🏪 Keyspace Info:")
            for db, info in keyspace_info.items():
                if db.startswith('db'):
                    print(f"   {db}: {info}")
        except Exception as e:
            print(f"   ❌ Keyspace info error: {e}")
        
    except Exception as e:
        print(f"❌ Connection Error: {e}")

def show_specific_key(key_name):
    """Show details of a specific key"""
    try:
        r = redis.Redis(host='localhost', port=6382, decode_responses=True)
        
        if not r.exists(key_name):
            print(f"❌ Key '{key_name}' does not exist")
            return
        
        key_type = r.type(key_name)
        print(f"\n🔍 Detailed view of '{key_name}' ({key_type}):")
        print("=" * 50)
        
        if key_type == 'hash':
            hash_data = r.hgetall(key_name)
            for field, value in hash_data.items():
                print(f"{field}: {value}")
        
        elif key_type == 'string':
            value = r.get(key_name)
            print(value)
        
        # Add other types as needed
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    quick_check()
    
    # Also show the mt5:status details specifically
    print("\n" + "="*50)
    show_specific_key("mt5:status")