"""
Services import helper module

This module provides a centralized way to import the services module
from the API layer, handling path resolution and import errors gracefully.
"""

import sys
import os
import importlib.util

def get_services_module():
    """
    Import and return the services module from api/apps/news_collector/
    
    Returns:
        services module or None if import fails
    """
    try:
        # Get current file directory
        current_dir = os.path.dirname(__file__)
        # Get project root directory  
        project_root = os.path.dirname(current_dir)
        # Construct path to services module
        services_file = os.path.join(project_root, 'api', 'apps', 'news_collector', 'services.py')
        
        if not os.path.exists(services_file):
            print(f"Services file not found: {services_file}")
            return None
            
        # Load module using importlib
        spec = importlib.util.spec_from_file_location("services", services_file)
        if spec is None:
            print("Could not create module spec for services")
            return None
            
        services_module = importlib.util.module_from_spec(spec)
        
        # Add the API directory to sys.path temporarily for dependencies
        api_path = os.path.join(project_root, 'api')
        if api_path not in sys.path:
            sys.path.insert(0, api_path)
            
        try:
            spec.loader.exec_module(services_module)
            return services_module
        finally:
            # Remove the API path to avoid side effects
            if api_path in sys.path:
                sys.path.remove(api_path)
                
    except Exception as e:
        print(f"Failed to import services module: {e}")
        return None

# Global services instance
_services = None

def get_services():
    """Get cached services module instance"""
    global _services
    if _services is None:
        _services = get_services_module()
    return _services
