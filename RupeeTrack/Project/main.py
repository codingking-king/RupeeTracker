import os
import uuid
import json
import datetime
import csv
import io
import re
from flask import (Flask, request, redirect, url_for, session,
                   render_template, flash, make_response, jsonify, g)
import locale
import firebase_admin
from firebase_admin import credentials, firestore, auth
from firebase_admin import exceptions as firebase_exceptions

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Developer override for budget lock - set to True to disable budget lock for testing
DEVELOPER_OVERRIDE_BUDGET_LOCK = False

# Initialize Firebase Admin SDK
print("🔥 Starting Firebase initialization...")
try:
    print("📁 Loading credentials from Project/firebase_credentials.json...")
    cred = credentials.Certificate("Project/firebase_credentials.json")
    print("🚀 Initializing Firebase Admin SDK...")
    firebase_admin.initialize_app(cred)
    print("📊 Creating Firestore client...")
    db = firestore.client()
    print("✅ Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"❌ Error initializing Firebase Admin SDK: {e}")
    print(f"❌ Error type: {type(e).__name__}")
    import traceback
    print(f"❌ Full traceback: {traceback.format_exc()}")
    # Exit or handle error appropriately if Firebase is critical
    db = None # Ensure db is None if initialization fails

# Set locale for currency formatting
try:
    locale.setlocale(locale.LC_ALL, 'en_IN.utf8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'English_India.1252')
    except locale.Error:
        print("Warning: Could not set locale for currency formatting.")

@app.template_filter('currencyformat')
def currencyformat_filter(value):
    """Formats a number as currency with commas."""
    try:
        return locale.format_string("%.2f", value, grouping=True)
    except (TypeError, ValueError):
        return value

@app.template_filter('comma_format')
def comma_format_filter(value):
    """Formats a number with commas for readability."""
    try:
        # This handles both integers and floats, formatting them with commas.
        if isinstance(value, (int, float)):
            return "{:,.2f}".format(value)
        return value
    except (TypeError, ValueError):
        return value

@app.template_filter('format_datetime')
def format_datetime_filter(value, format='%B %d, %Y %I:%M %p'):
    """Formats an ISO datetime string into a readable format."""
    if not value:
        return ""
    try:
        # Parse the ISO format string
        dt_object = datetime.datetime.fromisoformat(value)
        return dt_object.strftime(format)
    except (ValueError, TypeError):
        return value # Return original value if parsing fails

CATEGORIES = ["Food", "Transport", "Salary", "Bills", "Entertainment", "Housing"]

# Default user data - no authentication needed
DEFAULT_USER_DATA_STRUCTURE = {
    "name": "",
    "email": "",
    "transactions": [],
    "budget": {
        "monthly": 0,
        "categories": {},
        "history": [],
        "last_updated": None,
        "change_history": [] # New field for progressive lock
    },
    "goals": [],
    "settings": {
        "show_presets": False,
        "smart_suggestions": True,
        "show_confirmations": True
    },
    "journal_entries": []
}

def get_user_data_from_firestore(uid):
    """Get user data from Firestore."""
    if not db:
        print("Firestore client not initialized.")
        return None, None

    user_ref = db.collection('users').document(uid)
    user_doc = user_ref.get()

    if user_doc.exists:
        user_data = user_doc.to_dict()
        # Ensure all default fields exist for existing users
        for key, default_value in DEFAULT_USER_DATA_STRUCTURE.items():
            if key not in user_data:
                user_data[key] = default_value
            elif isinstance(default_value, dict) and isinstance(user_data[key], dict):
                for sub_key, sub_default_value in default_value.items():
                    if sub_key not in user_data[key]:
                        user_data[key][sub_key] = sub_default_value
        return user_data, user_ref
    else:
        # Create new user data with default structure
        user_data = DEFAULT_USER_DATA_STRUCTURE.copy()
        user_data['email'] = auth.get_user(uid).email # Populate email from Firebase Auth
        user_ref.set(user_data)
        return user_data, user_ref

def save_user_data_to_firestore(user_ref, user_data):
    """Save user data to Firestore."""
    if user_ref:
        user_ref.set(user_data)
    else:
        print("User reference not provided for saving data.")

# Middleware to get user from session or redirect to login
@app.before_request
def before_request():
    if request.endpoint in ['login', 'signup', 'welcome', 'static', 'verify_token']:
        return # Allow access to login, signup, welcome, verify_token, and static files

    if 'user_id' not in session:
        return redirect(url_for('welcome'))
    
    # Re-fetch user data on each request to ensure it's fresh
    user_id = session['user_id']
    user_data, user_ref = get_user_data_from_firestore(user_id)
    if not user_data:
        # If user data somehow disappears from Firestore, log out
        session.pop('user_id', None)
        flash('Your session has expired or user data not found. Please log in again.', 'error')
        return redirect(url_for('welcome'))
    
    # Store user_data and user_ref in Flask's global context for easy access in routes
    # This is a common pattern, but be mindful of potential performance implications for very high traffic
    # For this app's scale, it's acceptable.
    g.user = user_data
    g.user_ref = user_ref

@app.route("/welcome")
def welcome():
    return render_template('welcome.html')

@app.route("/signup", methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')

        if not email or not password or not name:
            flash('All fields are required.', 'error')
            return redirect(url_for('signup'))

        try:
            user = auth.create_user(email=email, password=password)
            
            # Create user document in Firestore with default data
            user_data = DEFAULT_USER_DATA_STRUCTURE.copy()
            user_data['name'] = name
            user_data['email'] = email
            db.collection('users').document(user.uid).set(user_data)

            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except firebase_exceptions.FirebaseError as e:
            if e.code == 'auth/email-already-exists':
                flash('Error creating account: This email is already in use. Please try logging in or use a different email.', 'error')
            else:
                flash(f'Error creating account: {e}', 'error')
            return redirect(url_for('signup'))
        except Exception as e:
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('signup'))
    return render_template('signup.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # This route's POST method is now primarily for handling redirects after client-side auth.
        # Client-side Firebase SDK handles email/password authentication and sends token to /verify_token.
        # If a direct POST to /login occurs (e.g., from a non-JS form submission),
        # it should redirect back to login with an error or rely on client-side JS.
        flash('Please use the client-side login form.', 'error')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/verify_token", methods=['POST'])
def verify_token():
    """Verify Firebase ID token and create/login user"""
    try:
        data = request.get_json()
        id_token = data.get('idToken')
        display_name = data.get('displayName', '')
        
        if not id_token:
            return jsonify({'success': False, 'error': 'No ID token provided'})
        
        # Verify the ID token (for email/password)
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email', '')
        
        if not uid:
            return jsonify({'success': False, 'error': 'Could not determine user ID'})
        # Check if user exists in Firestore
        user_data, user_ref = get_user_data_from_firestore(uid)
        
        if not user_data:
            # Create new user data
            user_data = DEFAULT_USER_DATA_STRUCTURE.copy()
            user_data['email'] = email # Will be None if phone-only auth
            user_data['name'] = display_name or decoded_token.get('name', '') if id_token else ''
            
            # Save to Firestore
            db.collection('users').document(uid).set(user_data)
        
        # Set session
        session['user_id'] = uid
        
        return jsonify({'success': True})
        
    except firebase_exceptions.FirebaseError as e:
        print(f"Firebase Token verification error: {e}")
        return jsonify({'success': False, 'error': str(e)})
    except Exception as e:
        print(f"General Token verification error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route("/logout")
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('welcome'))

@app.route("/", methods=['GET'])
def index():
    user = g.user
    user_ref = g.user_ref
    
    print(f"User data loaded: {user is not None}")
    
    # Get transactions safely
    transactions_all = user.get('transactions', [])
    print(f"Transactions count: {len(transactions_all)}")
    
    # Check and upgrade budget structure
    if 'budget' not in user or not isinstance(user.get('budget'), dict):
        user['budget'] = {
            'monthly': user.get('budget', 0) if isinstance(user.get('budget'), int) else 0,
            'categories': {},
            'history': [],
            'last_updated': None,
            'change_history': [] # Ensure this is initialized
        }
    user_budget = user['budget'].get('monthly', 0)

    # Get filter criteria from query parameters
    filter_category = request.args.get('filter_category')
    filter_type = request.args.get('filter_type')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    filters = {
        'category': filter_category,
        'type': filter_type,
        'start_date': start_date_str,
        'end_date': end_date_str
    }
    
    # Convert timestamps to datetime objects safely
    for tx in transactions_all:
        try:
            if 'timestamp' in tx:
                tx['timestamp_dt'] = datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S")
            else:
                tx['timestamp_dt'] = datetime.datetime.now()
        except:
            tx['timestamp_dt'] = datetime.datetime.now()

    transactions_filtered = transactions_all
    
    # Apply filters safely
    if filter_category and transactions_filtered:
        transactions_filtered = [tx for tx in transactions_filtered if tx.get('category') == filter_category]
    if filter_type and transactions_filtered:
        transactions_filtered = [tx for tx in transactions_filtered if tx.get('type') == filter_type]
    if start_date_str and transactions_filtered:
        try:
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
            transactions_filtered = [tx for tx in transactions_filtered if tx.get('timestamp_dt', datetime.datetime.now()).date() >= start_date]
        except:
            pass
    if end_date_str and transactions_filtered:
        try:
            end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
            transactions_filtered = [tx for tx in transactions_filtered if tx.get('timestamp_dt', datetime.datetime.now()).date() <= end_date]
        except:
            pass

    # Sort transactions safely
    if transactions_filtered:
        try:
            transactions_sorted = sorted(transactions_filtered, key=lambda x: x.get('timestamp_dt', datetime.datetime.now()), reverse=True)
        except:
            transactions_sorted = transactions_filtered
    else:
        transactions_sorted = []
    
    # Calculate balance safely
    balance = 0
    for tx in transactions_all:
        try:
            if tx.get('type') == 'income':
                balance += float(tx.get('amount', 0))
            elif tx.get('type') == 'expense':
                balance -= float(tx.get('amount', 0))
        except:
            pass

    # Chart Data Processing
    now = datetime.datetime.now()
    current_month_transactions = []
    
    for tx in transactions_all:
        try:
            if tx.get('timestamp_dt') and tx['timestamp_dt'].month == now.month and tx['timestamp_dt'].year == now.year:
                current_month_transactions.append(tx)
        except:
            pass

    # Pie chart data (Expenses by Category)
    expense_by_category = {}
    for tx in current_month_transactions:
        try:
            if tx.get('type') == 'expense':
                category = tx.get('category', 'Other')
                amount = float(tx.get('amount', 0))
                expense_by_category[category] = expense_by_category.get(category, 0) + amount
        except:
            pass
    
    pie_chart_labels = list(expense_by_category.keys())
    pie_chart_data = list(expense_by_category.values())

    # Bar chart data (Income vs Expense)
    monthly_income = 0
    monthly_expenses = 0
    
    for tx in current_month_transactions:
        try:
            amount = float(tx.get('amount', 0))
            if tx.get('type') == 'income':
                monthly_income += amount
            elif tx.get('type') == 'expense':
                monthly_expenses += amount
        except:
            pass

    if user_budget > 0 and monthly_expenses > user_budget:
        flash("You have exceeded your monthly budget!", 'error')

    today_date = now.strftime("%Y-%m-%d")

    # Calculate total income and expenses safely
    total_income_all = 0
    total_expenses_all = 0
    
    for tx in transactions_all:
        try:
            amount = float(tx.get('amount', 0))
            if tx.get('type') == 'income':
                total_income_all += amount
            elif tx.get('type') == 'expense':
                total_expenses_all += amount
        except:
            pass
    
    current_balance_all = total_income_all - total_expenses_all

    # Prepare data for JavaScript charts safely
    expense_categories_json = json.dumps({
        "labels": pie_chart_labels,
        "data": pie_chart_data
    })
    income_vs_expenses_json = json.dumps({
        "labels": ["Income", "Expenses"],
        "income": [monthly_income],
        "expenses": [monthly_expenses]
    })
    
    # Calculate Net Worth Trend
    net_worth_history = {}
    cumulative_balance = 0
    
    # Sort transactions by timestamp to calculate cumulative balance correctly
    transactions_for_net_worth = sorted(transactions_all, key=lambda x: x.get('timestamp_dt', datetime.datetime.min))

    for tx in transactions_for_net_worth:
        try:
            amount = float(tx.get('amount', 0))
            if tx.get('type') == 'income':
                cumulative_balance += amount
            elif tx.get('type') == 'expense':
                cumulative_balance -= amount
            
            # Group by month for net worth trend
            month_year = tx['timestamp_dt'].strftime('%Y-%m')
            net_worth_history[month_year] = cumulative_balance
        except:
            pass

    # Calculate Monthly Cash Flow Trend
    monthly_cash_flow = {}
    
    # Group transactions by month and calculate net income for each month
    for tx in transactions_all:
        try:
            amount = float(tx.get('amount', 0))
            month_year = tx['timestamp_dt'].strftime('%Y-%m')
            
            if month_year not in monthly_cash_flow:
                monthly_cash_flow[month_year] = {'income': 0, 'expense': 0}
            
            if tx.get('type') == 'income':
                monthly_cash_flow[month_year]['income'] += amount
            elif tx.get('type') == 'expense':
                monthly_cash_flow[month_year]['expense'] += amount
        except:
            pass

    # Calculate net cash flow for each month and sort by month
    cash_flow_labels = []
    cash_flow_data = []
    
    # Sort months chronologically
    sorted_months = sorted(monthly_cash_flow.keys())

    for month_year in sorted_months:
        net_amount = monthly_cash_flow[month_year]['income'] - monthly_cash_flow[month_year]['expense']
        cash_flow_labels.append(datetime.datetime.strptime(month_year, '%Y-%m').strftime('%b %Y')) # e.g., Jan 2025
        cash_flow_data.append(net_amount)

    monthly_cash_flow_json = json.dumps({
        "labels": cash_flow_labels,
        "data": cash_flow_data
    })

    # Calculate total savings from goals
    total_savings = sum(goal.get('saved_amount', 0) for goal in user.get('goals', []))

    # Get recent transactions for the dashboard table (e.g., last 5)
    recent_transactions = transactions_sorted[:5]

    return render_template('dashboard.html', 
                           user=user,
                           current_balance=current_balance_all, 
                           total_income=total_income_all,
                           total_expenses=total_expenses_all,
                           total_savings=total_savings, # Pass total savings
                           transactions=transactions_sorted, 
                           categories=CATEGORIES, 
                           filters=filters, 
                           budget={
                               'spent_amount': monthly_expenses,
                               'budget_amount': user_budget
                           },
                           monthly_income=monthly_income, 
                           monthly_expenses=monthly_expenses, 
                           expense_categories_json=expense_categories_json,
                           income_vs_expenses_json=income_vs_expenses_json,
                           net_worth_json=json.dumps({ # Pass net worth data
                               "labels": [datetime.datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in sorted(net_worth_history.keys())],
                               "data": [net_worth_history[m] for m in sorted(net_worth_history.keys())]
                           }),
                           monthly_cash_flow_json=monthly_cash_flow_json, # Pass new cash flow data
                           goals=user.get('goals', []), # Pass goals data
                           recent_transactions=recent_transactions, # Pass recent transactions
                           category_budgets=user['budget'].get('categories', {}), # Pass category budgets
                           current_month_category_expenses=expense_by_category, # Pass current month's category expenses
                           today_date=today_date,
                           user_budget=user_budget)

@app.route('/transactions', methods=['GET'])
def transactions_page():
    user = g.user
    user_ref = g.user_ref
    
    # Initialize user settings if they don't exist
    if 'settings' not in user:
        user['settings'] = {
            'show_presets': False,  # Default to False for better UX
            'smart_suggestions': True,
            'show_confirmations': True
        }
    
    transactions_all = user.get('transactions', [])
    
    # Convert timestamps to datetime objects safely
    for tx in transactions_all:
        try:
            if 'timestamp' in tx:
                tx['timestamp_dt'] = datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S")
            else:
                tx['timestamp_dt'] = datetime.datetime.now()
        except:
            tx['timestamp_dt'] = datetime.datetime.now()

    # Sort transactions safely
    if transactions_all:
        try:
            transactions_sorted = sorted(transactions_all, key=lambda x: x.get('timestamp_dt', datetime.datetime.now()), reverse=True)
        except:
            transactions_sorted = transactions_all
    else:
        transactions_sorted = []

    # Calculate total income and expenses safely
    total_income = 0
    total_expenses = 0
    
    for tx in transactions_all:
        try:
            amount = float(tx.get('amount', 0))
            if tx.get('type') == 'income':
                total_income += amount
            elif tx.get('type') == 'expense':
                total_expenses += amount
        except:
            pass
    
    current_balance = total_income - total_expenses

    return render_template('transactions.html', 
                           user=user,
                           transactions=transactions_sorted, 
                           categories=CATEGORIES, 
                           total_income=total_income,
                           total_expenses=total_expenses,
                           current_balance=current_balance,
                           transaction_to_edit_json='null')

def calculate_current_month_expenses(user):
    """Calculate current month's total expenses and category-wise expenses."""
    now = datetime.datetime.now()
    transactions = user.get('transactions', [])
    
    monthly_expenses = 0
    category_expenses = {}
    
    for tx in transactions:
        try:
            tx_date = datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S")
            if (tx_date.month == now.month and 
                tx_date.year == now.year and 
                tx.get('type') == 'expense'):
                
                amount = float(tx.get('amount', 0))
                monthly_expenses += amount
                
                category = tx.get('category', 'Other')
                category_expenses[category] = category_expenses.get(category, 0) + amount
        except:
            continue
    
    return monthly_expenses, category_expenses

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    user = g.user
    user_ref = g.user_ref

    try:
        transaction_date_str = request.form.get('transaction_date')
        description = request.form.get('description', '').strip()
        amount_str = request.form.get('amount')
        transaction_type = request.form.get('type')
        category = request.form.get('category')

        # Basic validation
        if not all([transaction_date_str, description, amount_str, transaction_type, category]):
            flash('All fields are required.', 'error')
            return redirect(url_for('transactions_page'))

        transaction_date = datetime.datetime.strptime(transaction_date_str, "%Y-%m-%d").date()
        
        # Server-side validation: Prevent future dates
        if transaction_date > datetime.date.today():
            flash('Transaction date cannot be in the future.', 'error')
            return redirect(url_for('transactions_page'))

        # Validate amount
        try:
            amount = float(amount_str)
            if amount <= 0:
                flash('Amount must be positive.', 'error')
                return redirect(url_for('transactions_page'))
        except ValueError:
            flash('Invalid amount format.', 'error')
            return redirect(url_for('transactions_page'))

        # STRONG BUDGET VALIDATION LOGIC - Only for expenses
        if transaction_type == 'expense':
            # Initialize budget structure if not present
            if 'budget' not in user or not isinstance(user.get('budget'), dict):
                user['budget'] = {
                    'monthly': 0,
                    'categories': {},
                    'history': [],
                    'last_updated': None
                }
            
            monthly_budget = user['budget'].get('monthly', 0)
            category_budgets = user['budget'].get('categories', {})
            
            # Only enforce budget if a budget is set (> 0)
            if monthly_budget > 0:
                # Calculate current month's expenses
                current_monthly_expenses, current_category_expenses = calculate_current_month_expenses(user)
                
                # Check if adding this expense would exceed monthly budget
                projected_monthly_expenses = current_monthly_expenses + amount
                
                if projected_monthly_expenses > monthly_budget:
                    remaining_budget = monthly_budget - current_monthly_expenses
                    flash(f'❌ Budget Exceeded! You only have ₹{remaining_budget:.2f} remaining in your monthly budget of ₹{monthly_budget:.2f}. This expense of ₹{amount:.2f} would exceed your budget by ₹{projected_monthly_expenses - monthly_budget:.2f}.', 'error')
                    return redirect(url_for('transactions_page'))
                
                # Check category-specific budget if set
                if category in category_budgets and category_budgets[category] > 0:
                    current_category_expense = current_category_expenses.get(category, 0)
                    category_budget = category_budgets[category]
                    projected_category_expense = current_category_expense + amount
                    
                    if projected_category_expense > category_budget:
                        remaining_category_budget = category_budget - current_category_expense
                        flash(f'❌ Category Budget Exceeded! You only have ₹{remaining_category_budget:.2f} remaining in your {category} budget of ₹{category_budget:.2f}. This expense would exceed your category budget by ₹{projected_category_expense - category_budget:.2f}.', 'error')
                        return redirect(url_for('transactions_page'))
                
                # Warning if approaching budget limits (80% threshold)
                budget_usage_percentage = (projected_monthly_expenses / monthly_budget) * 100
                if budget_usage_percentage >= 80 and budget_usage_percentage < 100:
                    remaining_budget = monthly_budget - projected_monthly_expenses
                    flash(f'⚠️ Budget Warning! After this transaction, you will have used {budget_usage_percentage:.1f}% of your monthly budget. Only ₹{remaining_budget:.2f} remaining.', 'warning')
                
                # Category warning if approaching category budget limits
                if category in category_budgets and category_budgets[category] > 0:
                    current_category_expense = current_category_expenses.get(category, 0)
                    category_budget = category_budgets[category]
                    projected_category_expense = current_category_expense + amount
                    category_usage_percentage = (projected_category_expense / category_budget) * 100
                    
                    if category_usage_percentage >= 80 and category_usage_percentage < 100:
                        remaining_category_budget = category_budget - projected_category_expense
                        flash(f'⚠️ Category Warning! After this transaction, you will have used {category_usage_percentage:.1f}% of your {category} budget. Only ₹{remaining_category_budget:.2f} remaining.', 'warning')

        # Create the transaction
        new_transaction = {
            "id": str(uuid.uuid4()),
            "description": description[:25],
            "amount": amount,
            "type": transaction_type,
            "category": category,
            "timestamp": datetime.datetime.combine(transaction_date, datetime.datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S")
        }

        user.setdefault('transactions', []).append(new_transaction)
        save_user_data_to_firestore(user_ref, user)
        
        # Success message with budget info for expenses
        if transaction_type == 'expense' and user['budget'].get('monthly', 0) > 0:
            current_monthly_expenses, _ = calculate_current_month_expenses(user)
            monthly_budget = user['budget'].get('monthly', 0)
            remaining_budget = monthly_budget - current_monthly_expenses
            flash(f'✅ Transaction added successfully! Monthly budget remaining: ₹{remaining_budget:.2f} of ₹{monthly_budget:.2f}', 'success')
        else:
            flash('✅ Transaction added successfully!', 'success')
            
        return redirect(url_for('transactions_page'))

    except ValueError:
        flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
        return redirect(url_for('transactions_page'))
    except Exception as e:
        print(f"Add transaction error: {e}")
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('transactions_page'))

@app.route('/edit_transaction/<tx_id>', methods=['GET', 'POST'])
def edit_transaction(tx_id):
    user = g.user
    user_ref = g.user_ref
    transactions = user.get('transactions', [])
    
    transaction_to_edit = next((tx for tx in transactions if tx.get('id') == tx_id), None)

    if not transaction_to_edit:
        flash('Transaction not found!', 'error')
        return redirect(url_for('transactions_page'))

    if request.method == 'POST':
        try:
            transaction_date_str = request.form.get('transaction_date')
            description = request.form.get('description', '').strip()
            amount_str = request.form.get('amount')
            transaction_type = request.form.get('type')
            category = request.form.get('category')

            if not all([transaction_date_str, description, amount_str, transaction_type, category]):
                flash('All fields are required.', 'error')
                return redirect(url_for('edit_transaction', tx_id=tx_id))

            transaction_date = datetime.datetime.strptime(transaction_date_str, "%Y-%m-%d").date()

            if transaction_date > datetime.date.today():
                flash('Transaction date cannot be in the future.', 'error')
                return redirect(url_for('edit_transaction', tx_id=tx_id))

            try:
                amount = float(amount_str)
                if amount <= 0:
                    flash('Amount must be positive.', 'error')
                    return redirect(url_for('edit_transaction', tx_id=tx_id))
            except ValueError:
                flash('Invalid amount format.', 'error')
                return redirect(url_for('edit_transaction', tx_id=tx_id))

            transaction_to_edit.update({
                'description': description[:25],
                'amount': amount,
                'type': transaction_type,
                'category': category,
                'timestamp': datetime.datetime.combine(transaction_date, datetime.datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S")
            })

            save_user_data_to_firestore(user_ref, user)
            flash('Transaction updated successfully!', 'success')
            return redirect(url_for('transactions_page'))

        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
            return redirect(url_for('edit_transaction', tx_id=tx_id))
        except Exception as e:
            print(f"Edit transaction error: {e}")
            flash('An unexpected error occurred. Please try again.', 'error')
            return redirect(url_for('edit_transaction', tx_id=tx_id))
    
    # For GET request, we pass the transaction data to the template
    # The template will use this data to pre-fill the edit form
    transaction_to_edit_json = json.dumps(transaction_to_edit)
    
    return render_template('transactions.html', 
                           user=user,
                           transactions=user.get('transactions', []),
                           categories=CATEGORIES,
                           transaction_to_edit_json=transaction_to_edit_json)

def get_progressive_lock_status(user):
    """Check budget lock status using Progressive Lock System."""
    # Developer override: If this flag is True, always return unlocked for testing
    DEVELOPER_OVERRIDE_BUDGET_LOCK = False
    if DEVELOPER_OVERRIDE_BUDGET_LOCK:
        return False, 0, "", 0 # False for locked, 0 for remaining time, "" for reason, 0 for lock level

    if 'budget' not in user:
        return False, 0, "", 0
    
    # Initialize budget change tracking if not present
    if 'change_history' not in user['budget']:
        user['budget']['change_history'] = []
    
    now = datetime.datetime.now()
    change_history = user['budget']['change_history']
    
    # Clean old history (older than 30 days)
    cutoff_date = now - datetime.timedelta(days=30)
    user['budget']['change_history'] = [
        change for change in change_history 
        if datetime.datetime.fromisoformat(change['date']) > cutoff_date
    ]
    change_history = user['budget']['change_history']
    
    if not change_history:
        return False, 0, "", 1  # First change - 24 hour lock
    
    # Count recent changes
    last_7_days = now - datetime.timedelta(days=7)
    last_30_days = now - datetime.timedelta(days=30)
    
    changes_last_7_days = len([
        change for change in change_history 
        if datetime.datetime.fromisoformat(change['date']) > last_7_days
    ])
    
    changes_last_30_days = len(change_history)
    
    # Get the most recent change
    if not change_history:
        return False, 0, "", 1
    
    last_change = max(change_history, key=lambda x: x['date'])
    last_change_date = datetime.datetime.fromisoformat(last_change['date'])
    time_since_last_change = now - last_change_date
    
    # Determine lock level and duration
    if changes_last_30_days >= 3:  # 4th+ change in 30 days
        lock_duration_hours = 24 * 30  # 30 days
        lock_level = 4
        lock_reason = f"You've made {changes_last_30_days} budget changes in the last 30 days. To maintain financial discipline, budget changes are locked for 30 days."
    elif changes_last_7_days >= 2:  # 3rd+ change in 7 days  
        lock_duration_hours = 24 * 7  # 7 days
        lock_level = 3
        lock_reason = f"You've made {changes_last_7_days} budget changes in the last 7 days. Budget changes are locked for 7 days to encourage stability."
    elif changes_last_7_days >= 1:  # 2nd change in 7 days
        lock_duration_hours = 48  # 48 hours
        lock_level = 2
        lock_reason = f"This is your 2nd budget change in 7 days. Budget changes are locked for 48 hours."
    else:  # First change or well-spaced changes
        lock_duration_hours = 24  # 24 hours
        lock_level = 1
        lock_reason = "Budget changes are locked for 24 hours to prevent impulsive modifications."
    
    # Check if still locked
    lock_duration_seconds = lock_duration_hours * 3600
    if time_since_last_change.total_seconds() < lock_duration_seconds:
        remaining_seconds = lock_duration_seconds - time_since_last_change.total_seconds()
        remaining_hours = remaining_seconds / 3600
        
        if remaining_hours >= 24:
            remaining_time = f"{remaining_hours/24:.1f} days"
        else:
            remaining_time = f"{remaining_hours:.1f} hours"
        
        return True, remaining_time, lock_reason, lock_level
    
    return False, 0, "", lock_level

@app.route('/budgets', methods=['GET', 'POST'])
def budgets_page():
    user = g.user
    user_ref = g.user_ref
    now = datetime.datetime.now()
    
    # Initialize budget structure if not present
    if 'budget' not in user or not isinstance(user.get('budget'), dict):
        user['budget'] = {
            'monthly': user.get('budget', 0) if isinstance(user.get('budget'), int) else 0,
            'categories': {},
            'history': [],
            'last_updated': None
        }

    # Check progressive lock status
    budget_locked, grace_period_remaining, budget_locked_reason, lock_level = get_progressive_lock_status(user)

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'set_monthly_budget':
            # Check if monthly budget is locked
            if budget_locked:
                lock_level_names = {1: "Level 1", 2: "Level 2", 3: "Level 3", 4: "Level 4"}
                flash(f'🔒 Budget Locked ({lock_level_names.get(lock_level, "")})! {budget_locked_reason}', 'error')
                return redirect(url_for('budgets_page'))
            
            try:
                monthly_budget = float(request.form.get('monthly_budget', 0))
                if monthly_budget < 0:
                    flash('Monthly budget cannot be negative.', 'error')
                else:
                    # Initialize change_history if not present
                    if 'change_history' not in user['budget']:
                        user['budget']['change_history'] = []
                    
                    # Record this change in history
                    previous_budget = user['budget'].get('monthly', 0)
                    change_entry = {
                        'date': now.isoformat(),
                        'previous_amount': previous_budget,
                        'new_amount': monthly_budget,
                        'change_reason': 'Manual update'
                    }
                    user['budget']['change_history'].append(change_entry)
                    
                    # Also keep the old history format for compatibility
                    if previous_budget > 0:
                        history_entry = {
                            'date': now.isoformat(),
                            'previous_amount': previous_budget,
                            'new_amount': monthly_budget,
                            'change_reason': 'Manual update'
                        }
                        user['budget']['history'].append(history_entry)
                    
                    user['budget']['monthly'] = monthly_budget
                    user['budget']['last_updated'] = now.isoformat()
                    save_user_data_to_firestore(user_ref, user)
                    
                    # Determine next lock duration based on change frequency
                    _, _, _, next_lock_level = get_progressive_lock_status(user)
                    lock_durations = {1: "24 hours", 2: "48 hours", 3: "7 days", 4: "30 days"}
                    next_duration = lock_durations.get(next_lock_level, "24 hours")
                    
                    if monthly_budget > 0:
                        flash(f'✅ Monthly budget set to ₹{monthly_budget:.2f}! Budget changes are now locked for {next_duration}. Category budgets can still be modified anytime.', 'success')
                    else:
                        flash('Monthly budget removed successfully.', 'success')
            except (ValueError, TypeError):
                flash('Invalid budget amount.', 'error')
        
        elif action == 'set_category_budget':
            # Category budgets can always be changed (no 48-hour restriction)
            try:
                category = request.form.get('category')
                amount = float(request.form.get('budget_amount', 0))

                if category and category in CATEGORIES:
                    if amount < 0:
                        flash('Category budget cannot be negative.', 'error')
                    else:
                        user['budget']['categories'][category] = amount
                        save_user_data_to_firestore(user_ref, user)
                        if amount > 0:
                            flash(f'✅ {category} budget set to ₹{amount:.2f}!', 'success')
                        else:
                            flash(f'{category} budget removed.', 'success')
                else:
                    flash('Invalid category.', 'error')
            except (ValueError, TypeError):
                flash('Invalid budget amount.', 'error')

        return redirect(url_for('budgets_page'))

    # Calculations for rendering the page
    current_budget = user['budget'].get('monthly', 0)
    category_budgets = user['budget'].get('categories', {})
    
    transactions = user.get('transactions', [])
    current_month_transactions = []
    
    for tx in transactions:
        try:
            tx_date = datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S")
            if tx_date.month == now.month and tx_date.year == now.year:
                current_month_transactions.append(tx)
        except:
            pass

    monthly_income = sum(float(tx['amount']) for tx in current_month_transactions if tx['type'] == 'income')
    monthly_expenses = sum(float(tx['amount']) for tx in current_month_transactions if tx['type'] == 'expense')

    category_expenses = {cat: 0 for cat in CATEGORIES}
    for tx in current_month_transactions:
        if tx['type'] == 'expense':
            category_expenses[tx['category']] = category_expenses.get(tx['category'], 0) + float(tx['amount'])

    remaining_budget = current_budget - monthly_expenses
    budget_usage_percentage = (monthly_expenses / current_budget * 100) if current_budget > 0 else 0
    total_allocated = sum(category_budgets.values())

    # Warning messages
    warning_message = ""
    warning_level = ""
    if current_budget > 0:
        if budget_usage_percentage >= 100:
            formatted_exceeded_amount = currencyformat_filter(abs(remaining_budget))
            warning_message = f"You have exceeded your monthly budget by ₹{formatted_exceeded_amount}."
            warning_level = "danger"
        elif budget_usage_percentage >= 90:
            formatted_remaining_amount = currencyformat_filter(remaining_budget)
            warning_message = f"You have used {budget_usage_percentage:.1f}% of your budget. Only ₹{formatted_remaining_amount} remaining."
            warning_level = "warning"

    # Calculate days since last update for display
    days_since_update = 0
    last_updated = None
    if user['budget'].get('last_updated'):
        try:
            last_updated_dt = datetime.datetime.fromisoformat(user['budget']['last_updated'])
            last_updated = last_updated_dt.strftime('%B %d, %Y at %I:%M %p')
            days_since_update = (now - last_updated_dt).days
        except:
            pass

    # --- Start of new logic for processed_budget_history ---
    processed_budget_history = []
    
    # Determine the budget for each month based on history
    budget_values_over_time = {}
    
    # Get all budget change events, sorted by date
    budget_changes = sorted(user['budget'].get('history', []), key=lambda x: datetime.datetime.fromisoformat(x['date']))
    
    # Initialize with the current budget if no history, or the earliest recorded budget
    initial_budget = user['budget'].get('monthly', 0)
    if budget_changes:
        # The 'previous_amount' of the very first change is the budget before any changes were recorded
        initial_budget = budget_changes[0]['previous_amount'] 
    
    # Create a list of all months from the earliest budget change or transaction to the current month
    earliest_date = None
    if transactions:
        earliest_tx_date = min(datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S") for tx in transactions if 'timestamp' in tx)
        if earliest_date is None or earliest_tx_date < earliest_date:
            earliest_date = earliest_tx_date
    if budget_changes:
        earliest_change_date = datetime.datetime.fromisoformat(budget_changes[0]['date'])
        if earliest_date is None or earliest_change_date < earliest_date:
            earliest_date = earliest_change_date
            
    if earliest_date is None: # No transactions or budget history, no past months to show
        sorted_months = []
    else:
        start_month = earliest_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        current_month_iter = start_month
        all_months_dt = []
        while current_month_iter <= end_month:
            all_months_dt.append(current_month_iter)
            # Move to next month
            if current_month_iter.month == 12:
                current_month_iter = current_month_iter.replace(year=current_month_iter.year + 1, month=1)
            else:
                current_month_iter = current_month_iter.replace(month=current_month_iter.month + 1)
        
        sorted_months = [m.strftime("%Y-%m") for m in all_months_dt]

    # Iterate through months and determine the effective budget for each
    for month_str in sorted_months:
        month_start_dt = datetime.datetime.strptime(month_str, "%Y-%m")
        
        # Find the latest budget change that occurred before or during this month
        effective_budget_for_month = initial_budget # Start with the very first budget
        for change in budget_changes:
            change_date = datetime.datetime.fromisoformat(change['date'])
            if change_date <= month_start_dt: # If change happened before or at the start of this month
                effective_budget_for_month = change['new_amount']
            elif change_date > month_start_dt: # Changes after this month's start are not relevant for this month
                break # Since budget_changes are sorted, we can break early
        
        budget_values_over_time[month_str] = effective_budget_for_month

    # Now, iterate through sorted months to build the history
    for month_str in sorted_months:
        month_start_dt = datetime.datetime.strptime(month_str, "%Y-%m")
        
        # Skip current month as it's handled by the main overview
        if month_start_dt.month == now.month and month_start_dt.year == now.year:
            continue

        monthly_expenses_sum = 0
        for tx in transactions:
            try:
                tx_date = datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S")
                if (tx_date.month == month_start_dt.month and 
                    tx_date.year == month_start_dt.year and 
                    tx.get('type') == 'expense'):
                    monthly_expenses_sum += float(tx.get('amount', 0))
            except:
                pass
        
        month_budget = budget_values_over_time.get(month_str, 0) # Use the determined budget for this month

        remaining = month_budget - monthly_expenses_sum
        usage_percentage = (monthly_expenses_sum / month_budget * 100) if month_budget > 0 else 0

        processed_budget_history.append({
            'month': month_start_dt.strftime("%B %Y"),
            'budget': month_budget,
            'expenses': monthly_expenses_sum,
            'remaining': remaining,
            'usage_percentage': usage_percentage
        })
    
    # Sort the processed history by date, descending
    processed_budget_history.sort(key=lambda x: datetime.datetime.strptime(x['month'], "%B %Y"), reverse=True)
    # --- End of new logic for processed_budget_history ---

    return render_template('budgets.html', 
                           user=user,
                           current_budget=current_budget,
                           category_budgets=category_budgets,
                           monthly_income=monthly_income,
                           monthly_expenses=monthly_expenses,
                           category_expenses=category_expenses,
                           remaining_budget=remaining_budget,
                           budget_usage_percentage=budget_usage_percentage,
                           total_allocated=total_allocated,
                           categories=CATEGORIES,
                           budget_history=processed_budget_history, # Pass the new processed history
                           current_month=now.strftime("%B %Y"),
                           can_update_budget=not budget_locked,
                           grace_period_remaining=grace_period_remaining,
                           budget_locked_reason=budget_locked_reason,
                           last_updated=last_updated,
                           days_since_update=days_since_update,
                           warning_message=warning_message,
                           warning_level=warning_level)

@app.route('/goals')
def goals():
    user = g.user
    user_ref = g.user_ref
    
    # Initialize goals if they don't exist
    if 'goals' not in user:
        user['goals'] = []
    
    # Calculate available balance (total balance minus allocated to goals)
    transactions = user.get('transactions', [])
    total_income = 0
    total_expenses = 0
    
    for tx in transactions:
        try:
            amount = float(tx.get('amount', 0))
            if tx.get('type') == 'income':
                total_income += amount
            elif tx.get('type') == 'expense':
                total_expenses += amount
        except:
            pass
    
    total_balance = total_income - total_expenses
    total_allocated = sum(goal.get('saved_amount', 0) for goal in user['goals'])
    available_balance = total_balance - total_allocated
    
    # Goal categories
    goal_categories = ['Emergency', 'Travel', 'Education', 'Technology', 'Health', 'Home', 'Investment', 'Entertainment', 'Vehicle', 'Other']
    
    return render_template('goals.html', 
                         user=user, 
                         goals=user['goals'],
                         available_balance=available_balance,
                         categories=goal_categories)

@app.route('/create_goal', methods=['POST'])
def create_goal():
    user = g.user
    user_ref = g.user_ref
    
    if 'goals' not in user:
        user['goals'] = []
    
    try:
        title = request.form['title'].strip()
        target_amount = float(request.form['target_amount'])
        category = request.form['category']
        deadline = request.form.get('deadline', '')
        
        if not title or target_amount <= 0:
            flash('Please provide valid goal details.', 'error')
            return redirect(url_for('goals'))
        
        # Validate deadline if provided
        if deadline:
            try:
                deadline_date = datetime.datetime.strptime(deadline, '%Y-%m-%d').date()
                if deadline_date <= datetime.date.today():
                    flash('Deadline must be in the future.', 'error')
                    return redirect(url_for('goals'))
            except ValueError:
                deadline = ''
        
        new_goal = {
            'id': str(uuid.uuid4()),
            'title': title,
            'target_amount': target_amount,
            'saved_amount': 0.0,
            'category': category,
            'deadline': deadline,
            'status': 'In Progress',
            'created_date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'transactions': []
        }
        
        user['goals'].append(new_goal)
        save_user_data_to_firestore(user_ref, user)
        flash('Goal created successfully!', 'success')
        
    except ValueError:
        flash('Please enter valid amounts.', 'error')
    except Exception as e:
        print(f"Create goal error: {e}")
        flash('An error occurred while creating the goal.', 'error')
    
    return redirect(url_for('goals'))

@app.route('/add_money/<goal_id>', methods=['POST'])
def add_money(goal_id):
    user = g.user
    user_ref = g.user_ref
    
    try:
        amount = float(request.form['amount'])
        
        if amount <= 0:
            flash('Amount to add must be positive.', 'error')
            return redirect(url_for('goals'))
            
        goal_found = False
        for goal in user['goals']:
            if goal['id'] == goal_id:
                goal_found = True
                
                # Calculate available balance (total balance minus allocated to goals)
                transactions = user.get('transactions', [])
                total_income = sum(float(tx.get('amount', 0)) for tx in transactions if tx.get('type') == 'income')
                total_expenses = sum(float(tx.get('amount', 0)) for tx in transactions if tx.get('type') == 'expense')
                total_balance = total_income - total_expenses
                total_allocated = sum(g.get('saved_amount', 0) for g in user['goals'])
                available_balance = total_balance - total_allocated
                
                remaining_to_goal = goal['target_amount'] - goal['saved_amount']
                
                if amount > available_balance:
                    flash(f'Insufficient available balance. You only have ₹{available_balance:.2f} available.', 'error')
                    return redirect(url_for('goals'))
                
                if amount > remaining_to_goal:
                    flash(f'Amount exceeds remaining goal target. You only need ₹{remaining_to_goal:.2f} to complete this goal.', 'error')
                    return redirect(url_for('goals'))
                
                goal['saved_amount'] += amount
                
                # Update goal status if completed
                if goal['saved_amount'] >= goal['target_amount']:
                    goal['status'] = 'Completed'
                    flash(f'🎉 Goal "{goal["title"]}" completed! Congratulations!', 'success')
                
                # Record transaction for the goal
                goal_transaction = {
                    'id': str(uuid.uuid4()),
                    'amount': amount,
                    'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'add_money_to_goal',
                    'balance_after': goal['saved_amount'] # Balance within the goal
                }
                goal.setdefault('transactions', []).append(goal_transaction)
                
                save_user_data_to_firestore(user_ref, user)
                flash(f'₹{amount:.2f} added to "{goal["title"]}" successfully!', 'success')
                break
        
        if not goal_found:
            flash('Goal not found.', 'error')
            
    except ValueError:
        flash('Please enter a valid amount.', 'error')
    except Exception as e:
        print(f"Add money to goal error: {e}")
        flash('An error occurred while adding money to the goal.', 'error')
    
    return redirect(url_for('goals'))

@app.route('/edit_goal/<goal_id>', methods=['POST'])
def edit_goal(goal_id):
    user = g.user
    user_ref = g.user_ref
    
    try:
        title = request.form['title'].strip()
        target_amount = float(request.form['target_amount'])
        category = request.form['category']
        deadline = request.form.get('deadline', '')
        
        if not title or target_amount <= 0:
            flash('Please provide valid goal details.', 'error')
            return redirect(url_for('goals'))
            
        # Validate deadline if provided
        if deadline:
            try:
                deadline_date = datetime.datetime.strptime(deadline, '%Y-%m-%d').date()
                if deadline_date <= datetime.date.today():
                    flash('Deadline must be in the future.', 'error')
                    return redirect(url_for('goals'))
            except ValueError:
                deadline = '' # Clear invalid deadline
        
        goal_found = False
        for goal in user['goals']:
            if goal['id'] == goal_id:
                goal_found = True
                goal['title'] = title
                goal['target_amount'] = target_amount
                goal['category'] = category
                goal['deadline'] = deadline
                
                # Update status if target amount is met or exceeded
                if goal['saved_amount'] >= goal['target_amount']:
                    goal['status'] = 'Completed'
                else:
                    goal['status'] = 'In Progress'
                    
                save_user_data_to_firestore(user_ref, user)
                flash('Goal updated successfully!', 'success')
                break
        
        if not goal_found:
            flash('Goal not found.', 'error')
            
    except ValueError:
        flash('Please enter valid amounts.', 'error')
    except Exception as e:
        print(f"Edit goal error: {e}")
        flash('An error occurred while updating the goal.', 'error')
    
    return redirect(url_for('goals'))

@app.route('/delete_goal/<goal_id>', methods=['POST'])
def delete_goal(goal_id):
    user = g.user
    user_ref = g.user_ref
    
    original_goals_count = len(user.get('goals', []))
    user['goals'] = [goal for goal in user.get('goals', []) if goal['id'] != goal_id]
    
    if len(user['goals']) < original_goals_count:
        save_user_data_to_firestore(user_ref, user)
        flash('Goal deleted successfully! Saved amount returned to available balance.', 'success')
    else:
        flash('Goal not found.', 'error')
        
    return redirect(url_for('goals'))

@app.route('/goal_transactions/<goal_id>', methods=['GET'])
def goal_transactions(goal_id):
    user = g.user
    
    transactions = []
    for goal in user.get('goals', []):
        if goal['id'] == goal_id:
            transactions = sorted(goal.get('transactions', []), key=lambda x: x['date'], reverse=True)
            break
            
    return jsonify(transactions)

@app.route('/profile')
def profile_page():
    user = g.user
    user_ref = g.user_ref
    transactions = user.get('transactions', [])
    
    # Calculate financial statistics
    total_income = 0
    total_expenses = 0
    income_count = 0
    expense_count = 0
    largest_expense = None
    largest_income = None
    category_totals = {}
    
    for tx in transactions:
        try:
            amount = float(tx.get('amount', 0))
            tx_type = tx.get('type', '')
            category = tx.get('category', 'Other')
            
            if tx_type == 'income':
                total_income += amount
                income_count += 1
                if largest_income is None or amount > largest_income['amount']:
                    largest_income = tx
            elif tx_type == 'expense':
                total_expenses += amount
                expense_count += 1
                if largest_expense is None or amount > largest_expense['amount']:
                    largest_expense = tx
                
                # Track category spending
                category_totals[category] = category_totals.get(category, 0) + amount
        except:
            pass
    
    balance = total_income - total_expenses
    total_transactions = len(transactions)
    
    # Find top spending category
    top_category = ('None', 0)
    if category_totals:
        top_category = max(category_totals.items(), key=lambda x: x[1])
    
    # Initialize user settings if they don't exist
    if 'settings' not in user:
        user['settings'] = {
            'show_presets': False,  # Default to False for better UX
            'smart_suggestions': True,
            'show_confirmations': True
        }
    
    # Initialize notes if they don't exist
    if 'notes' not in user:
        user['notes'] = []

    if 'journal_entries' not in user:
        user['journal_entries'] = []

    # Calculate total savings from goals
    total_savings = sum(goal.get('saved_amount', 0) for goal in user.get('goals', []))
    
    return render_template('profile.html', 
                         user=user,
                         total_income=total_income,
                         total_expenses=total_expenses,
                         balance=balance,
                         income_count=income_count,
                         expense_count=expense_count,
                         total_transactions=total_transactions,
                         largest_expense=largest_expense,
                         largest_income=largest_income,
                         top_category=top_category,
                         total_savings=total_savings)

@app.route('/delete_transaction/<tx_id>')
def delete_transaction(tx_id):
    user = g.user
    user_ref = g.user_ref
    transactions = user.get('transactions', [])
    
    # Find and remove the transaction
    for i, tx in enumerate(transactions):
        if tx.get('id') == tx_id:
            deleted_tx = transactions.pop(i)
            save_user_data_to_firestore(user_ref, user)
            flash(f'Transaction "{deleted_tx.get("description", "")}" deleted successfully!', 'success')
            break
    else:
        flash('Transaction not found!', 'error')
    
    return redirect(url_for('transactions_page'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    user = g.user
    user_ref = g.user_ref
    
    # Initialize settings if they don't exist
    if 'settings' not in user:
        user['settings'] = {
            'show_presets': False,  # Default to False for better UX
            'smart_suggestions': True,
            'show_confirmations': True
        }
    
    try:
        # Update settings based on form data
        user['settings']['show_presets'] = 'show_presets' in request.form
        user['settings']['smart_suggestions'] = 'smart_suggestions' in request.form
        user['settings']['show_confirmations'] = 'show_confirmations' in request.form
        
        # Save updated user data
        save_user_data_to_firestore(user_ref, user)
        flash('Settings updated successfully!', 'success')
        
    except Exception as e:
        print(f"Update settings error: {e}")
        flash('Error updating settings. Please try again.', 'error')
    
    return redirect(url_for('profile_page'))

@app.route('/update_journal', methods=['POST'])
def update_journal():
    user = g.user
    user_ref = g.user_ref
    
    try:
        entry_content = request.form.get('journal_entry', '').strip()
        if not entry_content:
            flash('Journal entry cannot be empty.', 'error')
            return redirect(url_for('profile_page'))

        new_entry = {
            'id': str(uuid.uuid4()),
            'content': entry_content,
            'date': datetime.datetime.now().isoformat()
        }
        
        if 'journal_entries' not in user:
            user['journal_entries'] = []
            
        user['journal_entries'].insert(0, new_entry) # Add new entry to the beginning of the list
        save_user_data_to_firestore(user_ref, user)
        flash('Journal entry added successfully!', 'success')
        
    except Exception as e:
        print(f"Update journal error: {e}")
        flash('Error updating journal. Please try again.', 'error')
        
    return redirect(url_for('profile_page'))

def main():
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)), debug=True)

if __name__ == "__main__":
    main()
