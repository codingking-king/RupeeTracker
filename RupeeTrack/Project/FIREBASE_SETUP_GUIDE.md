# Firebase Integration Setup Guide

Your Personal Finance Tracker is now fully integrated with Firebase! This guide will help you complete the setup.

## 🔥 Firebase Services Integrated

- **Firebase Authentication** - User login/signup with email/password and Google Sign-In
- **Cloud Firestore** - Real-time database for storing user data, transactions, budgets, and goals
- **Firebase Admin SDK** - Server-side operations and user management

## 📋 Setup Steps

### 1. Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Create a project" or "Add project"
3. Enter your project name (e.g., "personal-finance-tracker")
4. Enable Google Analytics (optional)
5. Click "Create project"

### 2. Enable Authentication

1. In your Firebase project, go to **Authentication** > **Sign-in method**
2. Enable the following providers:
   - **Email/Password** - Click and toggle "Enable"
   - **Google** - Click, toggle "Enable", and configure OAuth consent screen

### 3. Create Firestore Database

1. Go to **Firestore Database** > **Create database**
2. Choose **Start in test mode** (for development)
3. Select a location closest to your users
4. Click "Done"

### 4. Generate Service Account Key

1. Go to **Project Settings** (gear icon) > **Service accounts**
2. Click **"Generate new private key"**
3. Download the JSON file
4. Replace the content of `firebase_credentials.json` with your downloaded file

### 5. Get Web App Configuration

1. In **Project Settings** > **General** > **Your apps**
2. Click **"Add app"** > **Web app** (</> icon)
3. Register your app with a nickname
4. Copy the `firebaseConfig` object
5. Update the configuration in your HTML templates:

#### Update Login Template
Replace the `firebaseConfig` in `templates/login.html`:
```javascript
const firebaseConfig = {
    apiKey: "your-actual-api-key",
    authDomain: "your-project-id.firebaseapp.com",
    projectId: "your-project-id",
    storageBucket: "your-project-id.appspot.com",
    messagingSenderId: "your-sender-id",
    appId: "your-app-id"
};
```

#### Update Signup Template
Replace the `firebaseConfig` in `templates/signup.html` with the same configuration.

### 6. Configure Firestore Security Rules

In **Firestore Database** > **Rules**, replace the default rules with:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can only access their own data
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
  }
}
```

### 7. Update Firebase Credentials Path

In `main.py`, update the credentials path if needed:
```python
cred = credentials.Certificate("firebase_credentials.json")  # Remove "Project/" if needed
```

## 🚀 Features Now Available

### Authentication
- ✅ Email/Password signup and login
- ✅ Google Sign-In integration
- ✅ Secure token-based authentication
- ✅ Session management
- ✅ User profile management

### Data Storage
- ✅ Real-time data synchronization
- ✅ Automatic user data initialization
- ✅ Secure user data isolation
- ✅ Transaction history storage
- ✅ Budget and goal tracking
- ✅ Settings persistence

### Security
- ✅ Server-side token verification
- ✅ User data access control
- ✅ Secure API endpoints
- ✅ Session-based authentication

## 🔧 Configuration Files Updated

### Templates Created/Updated:
- `templates/welcome.html` - Landing page with authentication options
- `templates/login.html` - Login page with Firebase Auth integration
- `templates/signup.html` - Signup page with Firebase Auth integration

### Backend Updates:
- `main.py` - Added Firebase Admin SDK integration
- Added `/verify_token` endpoint for client-side authentication
- Updated middleware for proper session handling
- Enhanced user data management with Firestore

## 🧪 Testing Your Setup

1. **Start your application:**
   ```bash
   python main.py
   ```

2. **Test the flow:**
   - Visit `http://localhost:8080`
   - Try creating a new account
   - Test Google Sign-In
   - Add some transactions and verify they're saved
   - Check Firestore console to see your data

## 🔍 Troubleshooting

### Common Issues:

1. **"Firebase Admin SDK initialization failed"**
   - Ensure `firebase_credentials.json` contains valid service account key
   - Check file path in `main.py`

2. **"Authentication failed"**
   - Verify `firebaseConfig` in HTML templates matches your project
   - Ensure Authentication is enabled in Firebase Console

3. **"Permission denied" in Firestore**
   - Check Firestore security rules
   - Ensure user is properly authenticated

4. **Google Sign-In not working**
   - Configure OAuth consent screen in Google Cloud Console
   - Add authorized domains in Firebase Authentication settings

## 📱 Production Deployment

Before deploying to production:

1. **Update Firestore Rules** to production mode
2. **Configure authorized domains** in Firebase Authentication
3. **Set up proper environment variables** for sensitive data
4. **Enable Firebase App Check** for additional security
5. **Set up monitoring and analytics**

## 🎯 Next Steps

Your Firebase integration is complete! You can now:
- Deploy your app to a hosting service
- Add more authentication providers (Facebook, Twitter, etc.)
- Implement real-time features using Firestore listeners
- Add push notifications with Firebase Cloud Messaging
- Set up Firebase Analytics for user insights

## 📞 Support

If you encounter any issues:
1. Check the browser console for JavaScript errors
2. Check the Flask application logs
3. Verify your Firebase project configuration
4. Ensure all required services are enabled in Firebase Console

Your Personal Finance Tracker is now powered by Firebase! 🎉