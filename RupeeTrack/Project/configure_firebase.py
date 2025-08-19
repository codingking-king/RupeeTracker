#!/usr/bin/env python3
"""
Firebase Configuration Helper Script
This script helps you configure Firebase settings for your Personal Finance Tracker.
"""

import json
import os
import re

def update_firebase_config_in_templates():
    """Update Firebase configuration in HTML templates"""
    
    print("🔥 Firebase Configuration Helper")
    print("=" * 50)
    
    # Get Firebase config from user
    print("\nPlease enter your Firebase Web App configuration:")
    print("(You can find this in Firebase Console > Project Settings > General > Your apps)")
    print()
    
    api_key = input("API Key: ").strip()
    auth_domain = input("Auth Domain (project-id.firebaseapp.com): ").strip()
    project_id = input("Project ID: ").strip()
    storage_bucket = input("Storage Bucket (project-id.appspot.com): ").strip()
    messaging_sender_id = input("Messaging Sender ID: ").strip()
    app_id = input("App ID: ").strip()
    
    if not all([api_key, auth_domain, project_id, storage_bucket, messaging_sender_id, app_id]):
        print("❌ Error: All fields are required!")
        return False
    
    # Create the Firebase config object
    firebase_config = f'''const firebaseConfig = {{
            apiKey: "{api_key}",
            authDomain: "{auth_domain}",
            projectId: "{project_id}",
            storageBucket: "{storage_bucket}",
            messagingSenderId: "{messaging_sender_id}",
            appId: "{app_id}"
        }};'''
    
    # Update templates
    templates_to_update = ['templates/login.html', 'templates/signup.html']
    
    for template_path in templates_to_update:
        if os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Replace the Firebase config
                pattern = r'const firebaseConfig = \{[^}]+\};'
                updated_content = re.sub(pattern, firebase_config, content, flags=re.DOTALL)
                
                with open(template_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                
                print(f"✅ Updated {template_path}")
            except Exception as e:
                print(f"❌ Error updating {template_path}: {e}")
        else:
            print(f"⚠️  Template not found: {template_path}")
    
    return True

def validate_service_account_key():
    """Validate the Firebase service account key"""
    
    credentials_path = 'firebase_credentials.json'
    
    if not os.path.exists(credentials_path):
        print(f"❌ Service account key not found: {credentials_path}")
        print("Please download your service account key from Firebase Console and save it as 'firebase_credentials.json'")
        return False
    
    try:
        with open(credentials_path, 'r') as f:
            creds = json.load(f)
        
        required_fields = [
            'type', 'project_id', 'private_key_id', 'private_key',
            'client_email', 'client_id', 'auth_uri', 'token_uri'
        ]
        
        missing_fields = [field for field in required_fields if field not in creds]
        
        if missing_fields:
            print(f"❌ Service account key is missing required fields: {missing_fields}")
            return False
        
        if creds.get('type') != 'service_account':
            print("❌ Invalid service account key type")
            return False
        
        if 'your-project-id' in creds.get('project_id', ''):
            print("❌ Service account key contains placeholder values")
            print("Please replace firebase_credentials.json with your actual service account key")
            return False
        
        print(f"✅ Service account key is valid for project: {creds['project_id']}")
        return True
        
    except json.JSONDecodeError:
        print("❌ Invalid JSON in service account key file")
        return False
    except Exception as e:
        print(f"❌ Error validating service account key: {e}")
        return False

def check_dependencies():
    """Check if required dependencies are installed"""
    
    try:
        import firebase_admin
        print("✅ firebase-admin is installed")
        return True
    except ImportError:
        print("❌ firebase-admin is not installed")
        print("Run: pip install firebase-admin")
        return False

def main():
    """Main configuration function"""
    
    print("🚀 Personal Finance Tracker - Firebase Setup")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        return
    
    # Validate service account key
    print("\n📋 Checking service account key...")
    if not validate_service_account_key():
        print("\n📝 To get your service account key:")
        print("1. Go to Firebase Console > Project Settings > Service accounts")
        print("2. Click 'Generate new private key'")
        print("3. Save the downloaded file as 'firebase_credentials.json'")
        return
    
    # Update Firebase config in templates
    print("\n🔧 Configuring web app settings...")
    if update_firebase_config_in_templates():
        print("\n🎉 Firebase configuration completed successfully!")
        print("\n📋 Next steps:")
        print("1. Enable Authentication in Firebase Console")
        print("2. Create Firestore database")
        print("3. Configure Firestore security rules")
        print("4. Run your application: python main.py")
        print("\nFor detailed instructions, see FIREBASE_SETUP_GUIDE.md")
    else:
        print("\n❌ Configuration failed. Please check your inputs and try again.")

if __name__ == "__main__":
    main()