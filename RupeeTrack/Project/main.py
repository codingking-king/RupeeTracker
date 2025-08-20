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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()

DEVELOPER_OVERRIDE_BUDGET_LOCK = False

USER_DATA_FILE = 'user_data.json'

try:
    locale.setlocale(locale.LC_ALL, 'en_IN.utf8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'English_India.1252')
    except locale.Error:
        print("Warning: Could not set locale for currency formatting.")

@app.template_filter('currencyformat')
def currencyformat_filter(value):
    try:
        return locale.format_string("%.2f", value, grouping=True)
    except (TypeError, ValueError):
        return value

@app.template_filter('comma_format')
def comma_format_filter(value):
    try:
        if isinstance(value, (int, float)):
            return "{:,.2f}".format(value)
        return value
    except (TypeError, ValueError):
        return value

@app.template_filter('format_datetime')
def format_datetime_filter(value, format='%B %d, %Y %I:%M %p'):
    if not value:
        return ""
    try:
        dt_object = datetime.datetime.fromisoformat(value)
        return dt_object.strftime(format)
    except (ValueError, TypeError):
        return value

CATEGORIES = ["Food", "Transport", "Salary", "Bills", "Entertainment", "Housing"]

DEFAULT_USER_DATA_STRUCTURE = {
    "name": "Guest User",
    "email": "guest@example.com",
    "transactions": [],
    "budget": {
        "monthly": 0,
        "categories": {},
        "history": [],
        "last_updated": None,
        "change_history": []
    },
    "settings": {
        "show_presets": False,
        "smart_suggestions": True,
        "show_confirmations": True
    },
    "journal_entries": []
}

def load_user_data_from_json():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            try:
                data = json.load(f)
                merged_data = DEFAULT_USER_DATA_STRUCTURE.copy()
                merged_data.update(data)
                return merged_data
            except json.JSONDecodeError:
                print(f"Error decoding JSON from {USER_DATA_FILE}. Using default data.")
                return DEFAULT_USER_DATA_STRUCTURE.copy()
    return DEFAULT_USER_DATA_STRUCTURE.copy()

def save_user_data_to_json(user_data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(user_data, f, indent=4)

@app.before_request
def before_request():
    g.user = load_user_data_from_json()

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/dashboard", methods=['GET'])
def dashboard():
    user = g.user
    
    now = datetime.datetime.now()
    
    print(f"User data loaded: {user is not None}")
    
    transactions_all = user.get('transactions', [])
    print(f"Transactions count: {len(transactions_all)}")
    
    print(f"Current server time (now): {now}")
    
    if 'budget' not in user or not isinstance(user.get('budget'), dict):
        user['budget'] = {
            'monthly': user.get('budget', 0) if isinstance(user.get('budget'), int) else 0,
            'categories': {},
            'history': [],
            'last_updated': None,
            'change_history': []
        }
    monthly_budget = user['budget'].get('monthly', 0)

    pending_category_budgets = 0
    filled_category_budgets = 0
    total_category_allocated_budget = 0
    
    _, current_month_category_expenses = calculate_current_month_expenses(user)

    for category, budget_amount in user['budget'].get('categories', {}).items():
        total_category_allocated_budget += budget_amount
        if budget_amount > 0:
            spent_amount = current_month_category_expenses.get(category, 0)
            if spent_amount >= budget_amount:
                filled_category_budgets += budget_amount
            else:
                pending_category_budgets += (budget_amount - spent_amount)

    unallocated_budget = monthly_budget - total_category_allocated_budget
    if unallocated_budget < 0:
        unallocated_budget = 0

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
    
    for tx in transactions_all:
        try:
            if 'timestamp' in tx:
                tx['timestamp_dt'] = datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S")
            else:
                tx['timestamp_dt'] = datetime.datetime.now()
        except:
            tx['timestamp_dt'] = datetime.datetime.now()

    transactions_filtered = transactions_all
    
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

    if transactions_filtered:
        try:
            transactions_sorted = sorted(transactions_filtered, key=lambda x: x.get('timestamp_dt', datetime.datetime.now()), reverse=True)
        except:
            transactions_sorted = transactions_filtered
    else:
        transactions_sorted = []
    
    balance = 0
    for tx in transactions_all:
        try:
            if tx.get('type') == 'income':
                balance += float(tx.get('amount', 0))
            elif tx.get('type') == 'expense':
                balance -= float(tx.get('amount', 0))
        except:
            pass

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

    recent_transactions = transactions_sorted[:5]

    monthly_summary = get_monthly_summary(transactions_all)
    
    _, current_month_category_expenses = calculate_current_month_expenses(user)

    cash_flow_data = {month: data["income"] - data["expense"] for month, data in monthly_summary.items()}

    daily_summary = get_daily_summary(transactions_all)

    return render_template('dashboard.html', 
                           user=user,
                           current_balance=current_balance_all, 
                           total_income=total_income_all,
                           total_expenses=total_expenses_all,
                           transactions=transactions_sorted, 
                           categories=CATEGORIES, 
                           filters=filters, 
                           recent_transactions=recent_transactions,
                           category_budgets=user['budget'].get('categories', {}),
                           monthly_budget=monthly_budget,
                           pending_category_budgets=pending_category_budgets,
                           filled_category_budgets=filled_category_budgets,
                           total_category_allocated_budget=total_category_allocated_budget,
                           unallocated_budget=unallocated_budget,
                           user_budget=monthly_budget,
                           monthly_expenses=total_expenses_all,
                           monthly_summary_json=json.dumps(monthly_summary),
                           expense_breakdown_json=json.dumps(current_month_category_expenses),
                           cash_flow_json=json.dumps(cash_flow_data),
                           daily_summary_json=json.dumps(daily_summary))

def get_monthly_summary(transactions):
    monthly_data = {}
    now = datetime.datetime.now()
    
    for i in range(12):
        month_date = now - datetime.timedelta(days=30 * i)
        month_key = month_date.strftime("%Y-%m")
        monthly_data[month_key] = {"income": 0, "expense": 0, "net_flow": 0}

    for tx in transactions:
        try:
            tx_date = datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S")
            month_key = tx_date.strftime("%Y-%m")
            
            if month_key in monthly_data:
                amount = float(tx.get('amount', 0))
                tx_type = tx.get('type')
                
                if tx_type == 'income':
                    monthly_data[month_key]["income"] += amount
                    monthly_data[month_key]["net_flow"] += amount
                elif tx_type == 'expense':
                    monthly_data[month_key]["expense"] += amount
                    monthly_data[month_key]["net_flow"] -= amount
        except:
            continue
            
    sorted_monthly_data = dict(sorted(monthly_data.items()))
    
    return sorted_monthly_data

def get_daily_summary(transactions):
    daily_data = {}
    now = datetime.datetime.now()
    
    for i in range(30):
        day_date = now - datetime.timedelta(days=i)
        day_key = day_date.strftime("%Y-%m-%d")
        daily_data[day_key] = {"income": 0, "expense": 0}

    for tx in transactions:
        try:
            tx_date = datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S")
            day_key = tx_date.strftime("%Y-%m-%d")
            
            if day_key in daily_data:
                amount = float(tx.get('amount', 0))
                tx_type = tx.get('type')
                
                if tx_type == 'income':
                    daily_data[day_key]["income"] += amount
                elif tx_type == 'expense':
                    daily_data[day_key]["expense"] += amount
        except:
            continue
            
    sorted_daily_data = dict(sorted(daily_data.items()))
    
    return sorted_daily_data

@app.route('/transactions', methods=['GET'])
def transactions_page():
    user = g.user
    
    if 'settings' not in user:
        user['settings'] = {
            'show_presets': False,
            'smart_suggestions': True,
            'show_confirmations': True
        }
    
    transactions_all = user.get('transactions', [])
    
    for tx in transactions_all:
        try:
            if 'timestamp' in tx:
                tx['timestamp_dt'] = datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S")
            else:
                tx['timestamp_dt'] = datetime.datetime.now()
        except:
            tx['timestamp_dt'] = datetime.datetime.now()

    if transactions_all:
        try:
            transactions_sorted = sorted(transactions_all, key=lambda x: x.get('timestamp_dt', datetime.datetime.now()), reverse=True)
        except:
            transactions_sorted = transactions_all
    else:
        transactions_sorted = []

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
    
    try:
        transaction_date_str = request.form.get('transaction_date')
        description = request.form.get('description', '').strip()
        amount_str = request.form.get('amount')
        transaction_type = request.form.get('type')
        category = request.form.get('category')

        if not all([transaction_date_str, description, amount_str, transaction_type, category]):
            flash('All fields are required.', 'error')
            return redirect(url_for('transactions_page'))

        transaction_date = datetime.datetime.strptime(transaction_date_str, "%Y-%m-%d").date()
        
        if transaction_date > datetime.date.today():
            flash('Transaction date cannot be in the future.', 'error')
            return redirect(url_for('transactions_page'))

        try:
            amount = float(amount_str)
            if amount <= 0:
                flash('Amount must be positive.', 'error')
                return redirect(url_for('transactions_page'))
        except ValueError:
            flash('Invalid amount format.', 'error')
            return redirect(url_for('transactions_page'))

        if transaction_type == 'expense':
            if 'budget' not in user or not isinstance(user.get('budget'), dict):
                user['budget'] = {
                    'monthly': 0,
                    'categories': {},
                    'history': [],
                    'last_updated': None
                }
            
            monthly_budget = user['budget'].get('monthly', 0)
            category_budgets = user['budget'].get('categories', {})
            
            if monthly_budget > 0:
                current_monthly_expenses, current_category_expenses = calculate_current_month_expenses(user)
                
                projected_monthly_expenses = current_monthly_expenses + amount
                
                if projected_monthly_expenses > monthly_budget:
                    remaining_budget = monthly_budget - current_monthly_expenses
                    flash(f'❌ Budget Exceeded! You only have ₹{remaining_budget:.2f} remaining in your monthly budget of ₹{monthly_budget:.2f}. This expense of ₹{amount:.2f} would exceed your budget by ₹{projected_monthly_expenses - monthly_budget:.2f}.', 'error')
                    return redirect(url_for('transactions_page'))
                
                if category in category_budgets and category_budgets[category] > 0:
                    current_category_expense = current_category_expenses.get(category, 0)
                    category_budget = category_budgets[category]
                    projected_category_expense = current_category_expense + amount
                    
                    if projected_category_expense > category_budget:
                        remaining_category_budget = category_budget - current_category_expense
                        flash(f'❌ Category Budget Exceeded! You only have ₹{remaining_category_budget:.2f} remaining in your {category} budget of ₹{category_budget:.2f}. This expense would exceed your category budget by ₹{projected_category_expense - category_budget:.2f}.', 'error')
                        return redirect(url_for('transactions_page'))
                
                budget_usage_percentage = (projected_monthly_expenses / monthly_budget) * 100
                if budget_usage_percentage >= 80 and budget_usage_percentage < 100:
                    remaining_budget = monthly_budget - projected_monthly_expenses
                    flash(f'⚠️ Budget Warning! After this transaction, you will have used {budget_usage_percentage:.1f}% of your monthly budget. Only ₹{remaining_budget:.2f} remaining.', 'warning')
                
                if category in category_budgets and category_budgets[category] > 0:
                    current_category_expense = current_category_expenses.get(category, 0)
                    category_budget = category_budgets[category]
                    projected_category_expense = current_category_expense + amount
                    category_usage_percentage = (projected_category_expense / category_budget) * 100
                    
                    if category_usage_percentage >= 80 and category_usage_percentage < 100:
                        remaining_category_budget = category_budget - projected_category_expense
                        flash(f'⚠️ Category Warning! After this transaction, you will have used {category_usage_percentage:.1f}% of your {category} budget. Only ₹{remaining_category_budget:.2f} remaining.', 'warning')

        new_transaction = {
            "id": str(uuid.uuid4()),
            "description": description[:25],
            "amount": amount,
            "type": transaction_type,
            "category": category,
            "timestamp": datetime.datetime.combine(transaction_date, datetime.datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S")
        }

        user.setdefault('transactions', []).append(new_transaction)
        save_user_data_to_json(user)
        
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

            save_user_data_to_json(user)
            flash('Transaction updated successfully!', 'success')
            return redirect(url_for('transactions_page'))

        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
            return redirect(url_for('edit_transaction', tx_id=tx_id))
        except Exception as e:
            print(f"Edit transaction error: {e}")
            flash('An unexpected error occurred. Please try again.', 'error')
            return redirect(url_for('edit_transaction', tx_id=tx_id))
    
    transaction_to_edit_json = json.dumps(transaction_to_edit)
    
    return render_template('transactions.html', 
                           user=user,
                           transactions=user.get('transactions', []),
                           categories=CATEGORIES,
                           transaction_to_edit_json=transaction_to_edit_json)

def get_progressive_lock_status(user):
    DEVELOPER_OVERRIDE_BUDGET_LOCK = False
    if DEVELOPER_OVERRIDE_BUDGET_LOCK:
        return False, 0, "", 0

    if 'budget' not in user:
        return False, 0, "", 0
    
    if 'change_history' not in user['budget']:
        user['budget']['change_history'] = []
    
    now = datetime.datetime.now()
    change_history = user['budget']['change_history']
    
    cutoff_date = now - datetime.timedelta(days=30)
    user['budget']['change_history'] = [
        change for change in change_history 
        if datetime.datetime.fromisoformat(change['date']) > cutoff_date
    ]
    change_history = user['budget']['change_history']
    
    if not change_history:
        return False, 0, "", 1
    
    last_7_days = now - datetime.timedelta(days=7)
    last_30_days = now - datetime.timedelta(days=30)
    
    changes_last_7_days = len([
        change for change in change_history 
        if datetime.datetime.fromisoformat(change['date']) > last_7_days
    ])
    
    changes_last_30_days = len(change_history)
    
    if not change_history:
        return False, 0, "", 1
    
    last_change = max(change_history, key=lambda x: x['date'])
    last_change_date = datetime.datetime.fromisoformat(last_change['date'])
    time_since_last_change = now - last_change_date
    
    if changes_last_30_days >= 3:
        lock_duration_hours = 24 * 30
        lock_level = 4
        lock_reason = f"You've made {changes_last_30_days} budget changes in the last 30 days. To maintain financial discipline, budget changes are locked for 30 days."
    elif changes_last_7_days >= 2:
        lock_duration_hours = 24 * 7
        lock_level = 3
        lock_reason = f"You've made {changes_last_7_days} budget changes in the last 7 days. Budget changes are locked for 7 days to encourage stability."
    elif changes_last_7_days >= 1:
        lock_duration_hours = 48
        lock_level = 2
        lock_reason = f"This is your 2nd budget change in 7 days. Budget changes are locked for 48 hours."
    else:
        lock_duration_hours = 24
        lock_level = 1
        lock_reason = "Budget changes are locked for 24 hours to prevent impulsive modifications."
    
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
    now = datetime.datetime.now()
    
    if 'budget' not in user or not isinstance(user.get('budget'), dict):
        user['budget'] = {
            'monthly': user.get('budget', 0) if isinstance(user.get('budget'), int) else 0,
            'categories': {},
            'history': [],
            'last_updated': None
        }

    budget_locked, grace_period_remaining, budget_locked_reason, lock_level = get_progressive_lock_status(user)

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'set_monthly_budget':
            if budget_locked:
                lock_level_names = {1: "Level 1", 2: "Level 2", 3: "Level 3", 4: "Level 4"}
                flash(f'🔒 Budget Locked ({lock_level_names.get(lock_level, "")})! {budget_locked_reason}', 'error')
                return redirect(url_for('budgets_page'))
            
            try:
                monthly_budget = float(request.form.get('monthly_budget', 0))
                if monthly_budget < 0:
                    flash('Monthly budget cannot be negative.', 'error')
                else:
                    if 'change_history' not in user['budget']:
                        user['budget']['change_history'] = []
                    
                    previous_budget = user['budget'].get('monthly', 0)
                    change_entry = {
                        'date': now.isoformat(),
                        'previous_amount': previous_budget,
                        'new_amount': monthly_budget,
                        'change_reason': 'Manual update'
                    }
                    user['budget']['change_history'].append(change_entry)
                    
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
                    save_user_data_to_json(user)
                    
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
            try:
                category = request.form.get('category')
                amount = float(request.form.get('budget_amount', 0))

                if category and category in CATEGORIES:
                    if amount < 0:
                        flash('Category budget cannot be negative.', 'error')
                    else:
                        user['budget']['categories'][category] = amount
                        save_user_data_to_json(user)
                        if amount > 0:
                            flash(f'✅ {category} budget set to ₹{amount:.2f}!', 'success')
                        else:
                            flash(f'{category} budget removed.', 'success')
                else:
                    flash('Invalid category.', 'error')
            except (ValueError, TypeError):
                flash('Invalid budget amount.', 'error')

        return redirect(url_for('budgets_page'))

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

    days_since_update = 0
    last_updated = None
    if user['budget'].get('last_updated'):
        try:
            last_updated_dt = datetime.datetime.fromisoformat(user['budget']['last_updated'])
            last_updated = last_updated_dt.strftime('%B %d, %Y at %I:%M %p')
            days_since_update = (now - last_updated_dt).days
        except:
            pass

    processed_budget_history = []
    
    budget_values_over_time = {}
    
    budget_changes = sorted(user['budget'].get('history', []), key=lambda x: datetime.datetime.fromisoformat(x['date']))
    
    initial_budget = user['budget'].get('monthly', 0)
    if budget_changes:
        initial_budget = budget_changes[0]['previous_amount'] 
    
    earliest_date = None
    if transactions:
        earliest_tx_date = min(datetime.datetime.strptime(tx['timestamp'], "%Y-%m-%d %H:%M:%S") for tx in transactions if 'timestamp' in tx)
        if earliest_date is None or earliest_tx_date < earliest_date:
            earliest_date = earliest_tx_date
    if budget_changes:
        earliest_change_date = datetime.datetime.fromisoformat(budget_changes[0]['date'])
        if earliest_date is None or earliest_change_date < earliest_date:
            earliest_date = earliest_change_date
            
    if earliest_date is None:
        sorted_months = []
    else:
        start_month = earliest_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        current_month_iter = start_month
        all_months_dt = []
        while current_month_iter <= end_month:
            all_months_dt.append(current_month_iter)
            if current_month_iter.month == 12:
                current_month_iter = current_month_iter.replace(year=current_month_iter.year + 1, month=1)
            else:
                current_month_iter = current_month_iter.replace(month=current_month_iter.month + 1)
        
        sorted_months = [m.strftime("%Y-%m") for m in all_months_dt]

    for month_str in sorted_months:
        month_start_dt = datetime.datetime.strptime(month_str, "%Y-%m")
        
        effective_budget_for_month = initial_budget
        for change in budget_changes:
            change_date = datetime.datetime.fromisoformat(change['date'])
            if change_date <= month_start_dt:
                effective_budget_for_month = change['new_amount']
            elif change_date > month_start_dt:
                break
        
        budget_values_over_time[month_str] = effective_budget_for_month

    for month_str in sorted_months:
        month_start_dt = datetime.datetime.strptime(month_str, "%Y-%m")
        
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
        
        month_budget = budget_values_over_time.get(month_str, 0)

        remaining = month_budget - monthly_expenses_sum
        usage_percentage = (monthly_expenses_sum / month_budget * 100) if month_budget > 0 else 0

        processed_budget_history.append({
            'month': month_start_dt.strftime("%B %Y"),
            'budget': month_budget,
            'expenses': monthly_expenses_sum,
            'remaining': remaining,
            'usage_percentage': usage_percentage
        })
    
    processed_budget_history.sort(key=lambda x: datetime.datetime.strptime(x['month'], "%B %Y"), reverse=True)

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
                           budget_history=processed_budget_history,
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
    
    if 'goals' not in user:
        user['goals'] = []
    
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
    
    goal_categories = ['Emergency', 'Travel', 'Education', 'Technology', 'Health', 'Home', 'Investment', 'Entertainment', 'Vehicle', 'Other']
    
    return render_template('goals.html', 
                         user=user, 
                         goals=user['goals'],
                         available_balance=available_balance,
                         categories=goal_categories)

@app.route('/create_goal', methods=['POST'])
def create_goal():
    user = g.user
    
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
        save_user_data_to_json(user)
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
    
    try:
        amount = float(request.form['amount'])
        
        if amount <= 0:
            flash('Amount to add must be positive.', 'error')
            return redirect(url_for('goals'))
            
        goal_found = False
        for goal in user['goals']:
            if goal['id'] == goal_id:
                goal_found = True
                
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
                
                if goal['saved_amount'] >= goal['target_amount']:
                    goal['status'] = 'Completed'
                    flash(f'🎉 Goal "{goal["title"]}" completed! Congratulations!', 'success')
                
                goal_transaction = {
                    'id': str(uuid.uuid4()),
                    'amount': amount,
                    'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'type': 'add_money_to_goal',
                    'balance_after': goal['saved_amount']
                }
                goal.setdefault('transactions', []).append(goal_transaction)
                
                save_user_data_to_json(user)
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
    
    try:
        title = request.form['title'].strip()
        target_amount = float(request.form['target_amount'])
        category = request.form['category']
        deadline = request.form.get('deadline', '')
        
        if not title or target_amount <= 0:
            flash('Please provide valid goal details.', 'error')
            return redirect(url_for('goals'))
            
        if deadline:
            try:
                deadline_date = datetime.datetime.strptime(deadline, '%Y-%m-%d').date()
                if deadline_date <= datetime.date.today():
                    flash('Deadline must be in the future.', 'error')
                    return redirect(url_for('goals'))
            except ValueError:
                deadline = ''
        
        goal_found = False
        for goal in user['goals']:
            if goal['id'] == goal_id:
                goal_found = True
                goal['title'] = title
                goal['target_amount'] = target_amount
                goal['category'] = category
                goal['deadline'] = deadline
                
                if goal['saved_amount'] >= goal['target_amount']:
                    goal['status'] = 'Completed'
                else:
                    goal['status'] = 'In Progress'
                    
                save_user_data_to_json(user)
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
    
    original_goals_count = len(user.get('goals', []))
    user['goals'] = [goal for goal in user.get('goals', []) if goal['id'] != goal_id]
    
    if len(user['goals']) < original_goals_count:
        save_user_data_to_json(user)
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
    transactions = user.get('transactions', [])
    
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
                
                category_totals[category] = category_totals.get(category, 0) + amount
        except:
            pass
    
    balance = total_income - total_expenses
    total_transactions = len(transactions)
    
    top_category = ('None', 0)
    if category_totals:
        top_category = max(category_totals.items(), key=lambda x: x[1])
    
    if 'settings' not in user:
        user['settings'] = {
            'show_presets': False,
            'smart_suggestions': True,
            'show_confirmations': True
        }
    
    if 'notes' not in user:
        user['notes'] = []

    if 'journal_entries' not in user:
        user['journal_entries'] = []

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
    transactions = user.get('transactions', [])
    
    for i, tx in enumerate(transactions):
        if tx.get('id') == tx_id:
            deleted_tx = transactions.pop(i)
            save_user_data_to_json(user)
            flash(f'Transaction "{deleted_tx.get("description", "")}" deleted successfully!', 'success')
            break
    else:
        flash('Transaction not found!', 'error')
    
    return redirect(url_for('transactions_page'))

@app.route('/update_settings', methods=['POST'])
def update_settings():
    user = g.user
    
    if 'settings' not in user:
        user['settings'] = {
            'show_presets': False,
            'smart_suggestions': True,
            'show_confirmations': True
        }
    
    try:
        user['settings']['show_presets'] = 'show_presets' in request.form
        user['settings']['smart_suggestions'] = 'smart_suggestions' in request.form
        user['settings']['show_confirmations'] = 'show_confirmations' in request.form
        
        save_user_data_to_json(user)
        flash('Settings updated successfully!', 'success')
        
    except Exception as e:
        print(f"Update settings error: {e}")
        flash('Error updating settings. Please try again.', 'error')
    
    return redirect(url_for('profile_page'))

@app.route('/update_journal', methods=['POST'])
def update_journal():
    user = g.user
    
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
            
        user['journal_entries'].insert(0, new_entry)
        save_user_data_to_json(user)
        flash('Journal entry added successfully!', 'success')
        
    except Exception as e:
        print(f"Update journal error: {e}")
        flash('Error updating journal. Please try again.', 'error')
        
    return redirect(url_for('profile_page'))

def main():
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8080)), debug=True)

if __name__ == "__main__":
    main()
