#!/usr/bin/env python3
"""
Firebase Integration Test Script
This script tests the Firebase connection and basic functionality.
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, auth

def test_firebase_connection():
    """Test Firebase Admin SDK connection"""
    
    print("🔥 Testing Firebase Integration")
    print("=" * 40)
    
    # Test 1: Check credentials file
    print("\n1. Checking Firebase credentials...")
    
    credentials_path = 'firebase_credentials.json'
    if not os.path.exists(credentials_path):
        print("❌ firebase_credentials.json not found")
        return False
    
    try:
        with open(credentials_path, 'r') as f:
            creds_data = json.load(f)
        
        if 'your-project-id' in creds_data.get('project_id', ''):
            print("❌ Credentials file contains placeholder values")
            print("Please replace with your actual Firebase service account key")
            return False
        
        print(f"✅ Credentials file found for project: {creds_data['project_id']}")
    except Exception as e:
        print(f"❌ Error reading credentials: {e}")
        return False
    
    # Test 2: Initialize Firebase Admin SDK
    print("\n2. Initializing Firebase Admin SDK...")
    
    try:
        # Check if already initialized
        try:
            firebase_admin.get_app()
            print("✅ Firebase Admin SDK already initialized")
        except ValueError:
            # Not initialized, so initialize it
            cred = credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin SDK initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Firebase Admin SDK: {e}")
        return False
    
    # Test 3: Test Firestore connection
    print("\n3. Testing Firestore connection...")
    
    try:
        db = firestore.client()
        
        # Try to write a test document
        test_ref = db.collection('test').document('connection_test')
        test_ref.set({
            'message': 'Firebase connection test',
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        # Try to read it back
        doc = test_ref.get()
        if doc.exists:
            print("✅ Firestore read/write test successful")
            
            # Clean up test document
            test_ref.delete()
            print("✅ Test document cleaned up")
        else:
            print("❌ Failed to read test document")
            return False
            
    except Exception as e:
        print(f"❌ Firestore connection failed: {e}")
        print("Make sure you have created a Firestore database in your Firebase project")
        return False
    
    # Test 4: Test Authentication service
    print("\n4. Testing Firebase Authentication...")
    
    try:
        # Try to list users (this will work even with no users)
        users = auth.list_users(max_results=1)
        print("✅ Firebase Authentication service accessible")
    except Exception as e:
        print(f"❌ Firebase Authentication test failed: {e}")
        print("Make sure Authentication is enabled in your Firebase project")
        return False
    
    print("\n🎉 All Firebase tests passed!")
    print("\n📋 Your Firebase integration is working correctly!")
    print("You can now run your application with: python main.py")
    
    return True

def show_project_info():
    """Show Firebase project information"""
    
    try:
        with open('firebase_credentials.json', 'r') as f:
            creds = json.load(f)
        
        print("\n📊 Firebase Project Information:")
        print(f"Project ID: {creds.get('project_id', 'N/A')}")
        print(f"Client Email: {creds.get('client_email', 'N/A')}")
        print(f"Auth URI: {creds.get('auth_uri', 'N/A')}")
        
    except Exception as e:
        print(f"Could not read project info: {e}")

def main():
    """Main test function"""
    
    if test_firebase_connection():
        show_project_info()
        
        print("\n🚀 Ready to start your Personal Finance Tracker!")
        print("\nTo run your application:")
        print("  python main.py")
        print("\nThen visit: http://localhost:8080")
    else:
        print("\n❌ Firebase setup incomplete.")
        print("\nPlease check:")
        print("1. Firebase credentials are properly configured")
        print("2. Firestore database is created")
        print("3. Authentication is enabled")
        print("\nSee FIREBASE_SETUP_GUIDE.md for detailed instructions")

if __name__ == "__main__":
    main()