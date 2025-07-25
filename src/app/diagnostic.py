"""
Diagnostic endpoint to identify the exact model import error.
This will be accessible via /diagnostic on your deployed app.
"""

from fastapi import APIRouter
import traceback
import sys

router = APIRouter()

@router.get("/diagnostic")
async def diagnostic_models():
    """
    Test model imports one by one to identify the exact error.
    This endpoint will show us which model is causing the crash.
    """
    results = {
        "status": "running",
        "tests": [],
        "error": None,
        "success": False
    }
    
    try:
        # Test 1: Basic imports
        results["tests"].append({
            "test": "Basic imports (uuid, datetime, typing)",
            "status": "testing"
        })
        
        import uuid
        from datetime import datetime
        from typing import Optional, List, TYPE_CHECKING
        
        results["tests"][-1]["status"] = "✅ PASSED"
        
        # Test 2: SQLModel imports
        results["tests"].append({
            "test": "SQLModel imports",
            "status": "testing"
        })
        
        from sqlmodel import SQLModel, Field, Relationship
        
        results["tests"][-1]["status"] = "✅ PASSED"
        
        # Test 3: Individual model imports
        models_to_test = [
            ("User", "src.app.models.user"),
            ("Profile", "src.app.models.profile"),
            ("OAuthAccount", "src.app.models.oauth"),
            ("PasswordReset", "src.app.models.password_reset"),
            ("Course", "src.app.models.course"),
            ("Video", "src.app.models.video"),
            ("Enrollment", "src.app.models.enrollment"),
            ("EnrollmentApplication", "src.app.models.enrollment_application"),
            ("Assignment", "src.app.models.assignment"),
            ("Quiz", "src.app.models.quiz"),
        ]
        
        for model_name, module_path in models_to_test:
            test_entry = {
                "test": f"Import {model_name}",
                "status": "testing",
                "module": module_path
            }
            results["tests"].append(test_entry)
            
            try:
                # Clear any cached imports to get fresh results
                if module_path in sys.modules:
                    del sys.modules[module_path]
                
                __import__(module_path)
                test_entry["status"] = "✅ PASSED"
                
            except Exception as e:
                test_entry["status"] = "❌ FAILED"
                test_entry["error"] = str(e)
                test_entry["traceback"] = traceback.format_exc()
                
                # Stop at first failure to isolate the problem
                results["error"] = f"Model {model_name} failed to import: {str(e)}"
                results["failed_model"] = model_name
                results["failed_traceback"] = traceback.format_exc()
                return results
        
        # Test 4: Bulk import test
        results["tests"].append({
            "test": "Bulk import from __init__.py",
            "status": "testing"
        })
        
        from src.app.models import *
        results["tests"][-1]["status"] = "✅ PASSED"
        
        # Test 5: SQLAlchemy mapper configuration
        results["tests"].append({
            "test": "SQLAlchemy mapper configuration",
            "status": "testing"
        })
        
        from sqlalchemy.orm import configure_mappers
        configure_mappers()
        results["tests"][-1]["status"] = "✅ PASSED"
        
        results["status"] = "completed"
        results["success"] = True
        results["message"] = "🎉 ALL TESTS PASSED! Models are working correctly."
        
    except Exception as e:
        results["status"] = "failed"
        results["error"] = str(e)
        results["traceback"] = traceback.format_exc()
        results["message"] = f"💥 DIAGNOSTIC FAILED: {str(e)}"
    
    return results
