#!/usr/bin/env python3
"""
Diagnostic script to isolate and identify the exact error in model imports.
This will show us the precise line and file causing the crash.
"""

import sys
import traceback

print("🔍 Starting model import diagnostics...")
print("=" * 50)

try:
    print("Step 1: Testing basic imports...")
    import uuid
    from datetime import datetime
    from typing import Optional, List, TYPE_CHECKING
    print("✅ Basic imports successful")
    
    print("\nStep 2: Testing SQLModel imports...")
    from sqlmodel import SQLModel, Field, Relationship
    print("✅ SQLModel imports successful")
    
    print("\nStep 3: Testing individual model imports...")
    
    # Test each model one by one to isolate the problematic one
    models_to_test = [
        ("User", "src.app.models.user"),
        ("Course", "src.app.models.course"), 
        ("Enrollment", "src.app.models.enrollment"),
        ("EnrollmentApplication", "src.app.models.enrollment_application"),
        ("Assignment", "src.app.models.assignment"),
        ("Quiz", "src.app.models.quiz"),
        ("Profile", "src.app.models.profile"),
        ("OAuthAccount", "src.app.models.oauth"),
        ("PasswordReset", "src.app.models.password_reset"),
    ]
    
    for model_name, module_path in models_to_test:
        try:
            print(f"  Testing {model_name}...")
            __import__(module_path)
            print(f"  ✅ {model_name} imported successfully")
        except Exception as e:
            print(f"  ❌ {model_name} FAILED: {str(e)}")
            print(f"  📋 Full traceback for {model_name}:")
            traceback.print_exc()
            print("-" * 30)
    
    print("\nStep 4: Testing bulk import from __init__.py...")
    from src.app.models import *
    print("✅ Bulk import successful")
    
    print("\nStep 5: Testing SQLAlchemy mapper configuration...")
    from sqlalchemy.orm import configure_mappers
    configure_mappers()
    print("✅ Mapper configuration successful")
    
    print("\n🎉 ALL TESTS PASSED! Models are working correctly.")
    
except Exception as e:
    print(f"\n💥 DIAGNOSTIC FAILED: {str(e)}")
    print("\n📋 FULL ERROR TRACEBACK:")
    traceback.print_exc()
    print("\n" + "=" * 50)
    print("☝️  This is the exact error causing your application to crash!")
