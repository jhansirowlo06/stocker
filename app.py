from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import uuid
import hashlib
import time

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_stocker' # Used for session management

# --- Mock Database Structures (In-memory for simplicity) ---

# Hash a password
def hash_password(password):
    """Hashes a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

# Mock Users: id, username, email, password, role, cash_balance
USERS = {
    # Default Admin
    'admin_1': {
        'id': 'admin_1',
        'username': 'AdminUser',
        'email': 'admin@stocker.com',
        'password': hash_password('adminpass'),
        'role': 'Admin',
        'cash_balance': 0.00
    },
    # Default Trader
    'trader_1': {
        'id': 'trader_1',
        'username': 'TraderVinay',
        'email': 'vinay@trader.com',
        'password': hash_password('traderpass'),
        'role': 'Trader',
        'cash_balance': 10000.00 # This will be updated by mock transactions below
    },
    # Another mock trader for diverse transactions
    'trader_2': {
        'id': 'trader_2',
        'username': 'JaneDoe',
        'email': 'jane@trader.com',
        'password': hash_password('janepass'),
        'role': 'Trader',
        'cash_balance': 10000.00 # This will be updated by mock transactions below
    }
}

# Mock Stocks (Simulated Market Data)
STOCKS = {
    'GOOGL': {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'price': 1500.00, 'industry': 'Tech'},
    'TSLA': {'symbol': 'TSLA', 'name': 'Tesla, Inc.', 'price': 650.00, 'industry': 'Automotive'},
    'MSFT': {'symbol': 'MSFT', 'name': 'Microsoft Corp', 'price': 300.00, 'industry': 'Tech'},
    'JPM': {'symbol': 'JPM', 'name': 'JP Morgan Chase', 'price': 150.00, 'industry': 'Finance'},
    'XOM': {'symbol': 'XOM', 'name': 'Exxon Mobil Corp', 'price': 110.00, 'industry': 'Energy'},
}

# Mock Portfolio: {user_id: {symbol: {'quantity': N, 'avg_buy_price': P}}}
PORTFOLIOS = {} 


# Mock Transactions: Stores records of all buys and sells
TRANSACTIONS = [
    {
        'id': 't0001',
        'user_id': 'trader_1',
        'username': 'TraderVinay',
        'action': 'BUY',
        'stock': 'MSFT',
        'quantity': 10,
        'price': 250.00,
        'total': 2500.00,
        'status': 'Completed',
        'date': '2023-10-01 10:15:00'
    },
    {
        'id': 't0002',
        'user_id': 'trader_1',
        'username': 'TraderVinay',
        'action': 'BUY',
        'stock': 'JPM',
        'quantity': 50,
        'price': 140.00,
        'total': 7000.00,
        'status': 'Completed',
        'date': '2023-10-01 10:30:00'
    },
    {
        'id': 't0003',
        'user_id': 'trader_2',
        'username': 'JaneDoe',
        'action': 'BUY',
        'stock': 'GOOGL',
        'quantity': 2,
        'price': 1450.00,
        'total': 2900.00,
        'status': 'Completed',
        'date': '2023-10-02 11:00:00'
    },
    {
        'id': 't0004',
        'user_id': 'trader_1',
        'username': 'TraderVinay',
        'action': 'SELL',
        'stock': 'JPM',
        'quantity': 10,
        'price': 155.00,
        'total': 1550.00,
        'status': 'Completed',
        'date': '2023-10-03 14:45:00'
    },
    {
        'id': 't0005',
        'user_id': 'trader_2',
        'username': 'JaneDoe',
        'action': 'BUY',
        'stock': 'TSLA',
        'quantity': 5,
        'price': 600.00,
        'total': 3000.00,
        'status': 'Completed',
        'date': '2023-10-04 09:20:00'
    }
]

# --- Initialization of Portfolios and Cash Balances based on mock transactions ---

def initialize_mock_data():
    """Initializes portfolios and updates cash balances based on mock transactions."""
    
    # Reset cash for traders to ensure accurate calculation
    USERS['trader_1']['cash_balance'] = 10000.00
    USERS['trader_2']['cash_balance'] = 10000.00
    PORTFOLIOS.clear()

    for t in TRANSACTIONS:
        user_id = t['user_id']
        quantity = t['quantity']
        total = t['total']
        symbol = t['stock']
        
        # Update Cash Balance
        if t['action'] == 'BUY':
            USERS[user_id]['cash_balance'] -= total
        elif t['action'] == 'SELL':
            USERS[user_id]['cash_balance'] += total
            
        # Update Portfolio Holdings
        PORTFOLIOS.setdefault(user_id, {})
        holdings = PORTFOLIOS[user_id].setdefault(symbol, {'quantity': 0, 'avg_buy_price': 0.0})
        
        if t['action'] == 'BUY':
            # Calculate new average buy price
            old_total_cost = holdings['quantity'] * holdings['avg_buy_price']
            new_total_cost = old_total_cost + total
            new_total_quantity = holdings['quantity'] + quantity
            
            holdings['avg_buy_price'] = new_total_cost / new_total_quantity
            holdings['quantity'] = new_total_quantity
            
        elif t['action'] == 'SELL':
            # Selling reduces quantity (assuming sales are FIFO/LIFO, but we only track avg_buy_price)
            holdings['quantity'] -= quantity
            
            if holdings['quantity'] <= 0:
                del PORTFOLIOS[user_id][symbol]
                if not PORTFOLIOS[user_id]:
                    del PORTFOLIOS[user_id]
                    
initialize_mock_data() # Run the initialization function

# --- Helper Functions and Decorators ---

def get_user(user_id):
    """Retrieves user by ID."""
    return USERS.get(user_id)

@app.before_request
def load_logged_in_user():
    """Loads the user object into Flask's global context (g) before every request."""
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_user(user_id)
        # Add a check for user existence just in case the mock DB was reset
        if g.user is None:
             session.pop('user_id', None)


def login_required(role=None):
    """Decorator to enforce login and optional role."""
    def wrapper(func):
        def decorated_view(*args, **kwargs):
            if 'user_id' not in session or g.user is None:
                flash("Please log in to access this page.", 'error')
                return redirect(url_for('login'))
            user = g.user
            if role and user['role'] != role:
                flash(f"Access denied. You must be a {role}.", 'error')
                # Redirect based on role if logged in but unauthorized
                return redirect(url_for('admin_dashboard') if user['role'] == 'Admin' else url_for('trader_dashboard'))
            return func(*args, **kwargs)
        decorated_view.__name__ = func.__name__ # Needed for flask routing
        return decorated_view
    return wrapper
    
def calculate_portfolio_value(user_id):
    """Calculates the total market value of a user's portfolio."""
    total_value = 0.0
    if user_id in PORTFOLIOS:
        for symbol, holding in PORTFOLIOS[user_id].items():
            current_price = STOCKS.get(symbol, {'price': 0.0})['price']
            total_value += holding['quantity'] * current_price
    return total_value

# --- Routes ---

@app.route('/')
def index():
    """Landing Page (Home)"""
    return render_template('index.html', title="Welcome to STOCKER")

@app.route('/about')
def about_us():
    """About Us Page"""
    return render_template('about.html', title="About Us")

@app.route('/services')
def services():
    """Our Services Page"""
    return render_template('services.html', title="Our Services")

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User Registration Route"""
    if request.method == 'POST':
        email = request.form['email'].strip()
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form['role']
        
        # Simple validation
        if not all([email, username, password, role]):
            flash('All fields are required.', 'error')
            return redirect(url_for('register'))
        
        # Check if user already exists
        if any(u['email'] == email for u in USERS.values()):
            flash('Account with this email already exists.', 'error')
            return redirect(url_for('register'))

        user_id = str(uuid.uuid4())
        
        USERS[user_id] = {
            'id': user_id,
            'username': username,
            'email': email,
            'password': hash_password(password),
            'role': role,
            'cash_balance': 10000.00 if role == 'Trader' else 0.00
        }
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html', title="Create Account")

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User Login Route"""
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']
        role = request.form['role']
        
        hashed_password = hash_password(password)
        
        # Find user and verify credentials
        user_found = next((user for user in USERS.values() 
                           if user['email'] == email and 
                              user['password'] == hashed_password and 
                              user['role'] == role), None)
        
        if user_found:
            session['user_id'] = user_found['id']
            # g.user is set via @app.before_request on the next request
            flash('Login successful!', 'success')
            if role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('trader_dashboard'))
        else:
            flash('Invalid credentials or role selected.', 'error')
            return redirect(url_for('login'))

    return render_template('login.html', title="Welcome Back")

@app.route('/logout')
def logout():
    """User Logout Route"""
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# --- Admin Routes (Role: Admin) ---

@app.route('/admin_dashboard')
@login_required('Admin')
def admin_dashboard():
    """Admin Dashboard Overview"""
    total_traders = sum(1 for user in USERS.values() if user['role'] == 'Trader')
    total_transactions = len(TRANSACTIONS)
    
    # Calculate total market capitalization in the system
    total_market_value = sum(calculate_portfolio_value(uid) 
                             for uid, user in USERS.items() if user['role'] == 'Trader')

    context = {
        'total_traders': total_traders,
        'total_transactions': total_transactions,
        'total_market_value': f"${total_market_value:,.2f}"
    }
    return render_template('admin_dashboard.html', title="Admin Dashboard", **context)

@app.route('/view_traders')
@login_required('Admin')
def view_traders():
    """Admin: View all registered traders."""
    traders_list = []
    for user_id, user in USERS.items():
        if user['role'] == 'Trader':
            portfolio_value = calculate_portfolio_value(user_id)
            traders_list.append({
                'id': user_id[:8], # Truncated for display
                'username': user['username'],
                'email': user['email'],
                'portfolio_value': f"${portfolio_value:,.2f}"
            })
    
    return render_template('view_traders.html', 
                           title="View Traders", 
                           traders=traders_list, 
                           total_traders=len(traders_list))

@app.route('/view_transactions')
@login_required('Admin')
def view_transactions():
    """Admin: View all transaction records."""
    buy_count = sum(1 for t in TRANSACTIONS if t['action'] == 'BUY')
    sell_count = sum(1 for t in TRANSACTIONS if t['action'] == 'SELL')
    
    return render_template('view_transactions.html', 
                           title="Transaction Records", 
                           transactions=TRANSACTIONS,
                           total_transactions=len(TRANSACTIONS),
                           buy_count=buy_count,
                           sell_count=sell_count)

@app.route('/view_portfolios')
@login_required('Admin')
def view_portfolios():
    """Admin: View and manage all trader portfolios."""
    all_holdings = []
    total_portfolio_value = 0.0
    traders_with_portfolio = set()

    for user_id, holdings in PORTFOLIOS.items():
        user = USERS.get(user_id)
        if not user: continue
        
        traders_with_portfolio.add(user_id)
        
        for symbol, holding in holdings.items():
            stock = STOCKS.get(symbol, {'name': 'N/A', 'industry': 'N/A', 'price': 0.0})
            current_price = stock['price']
            market_value = holding['quantity'] * current_price
            total_portfolio_value += market_value
            
            all_holdings.append({
                'trader': user['username'],
                'stock_name': stock['name'],
                'symbol': symbol,
                'sector': stock['industry'],
                'quantity': holding['quantity'],
                'avg_buy_price': f"${holding['avg_buy_price']:,.2f}",
                'current_price': f"${current_price:,.2f}",
                'market_value': f"${market_value:,.2f}"
            })
            
    context = {
        'all_holdings': all_holdings,
        'total_value': f"${total_portfolio_value:,.2f}",
        'total_traders': len(traders_with_portfolio),
        'total_stocks_held': len(all_holdings) # Count of unique stock holdings across all traders
    }

    return render_template('view_portfolios.html', title="Portfolio Management", **context)


# --- Trader Routes (Role: Trader) ---

@app.route('/trader_dashboard')
@login_required('Trader')
def trader_dashboard():
    """Trader Dashboard: Overview and Portfolio Summary"""
    user = g.user # Use the globally loaded user
    user_id = user['id']
    
    portfolio_value = calculate_portfolio_value(user_id)
    
    # Get Market Overview (A sample of stocks for the dashboard)
    market_overview = [s for s in STOCKS.values()]

    context = {
        'username': user['username'],
        'cash_balance': f"${user['cash_balance']:,.2f}",
        'portfolio_value': f"${portfolio_value:,.2f}",
        'total_equity': f"${user['cash_balance'] + portfolio_value:,.2f}",
        'market_overview': market_overview
    }
    return render_template('trader_dashboard.html', title="Trader Dashboard", **context)

@app.route('/available_stocks')
@login_required('Trader')
def available_stocks():
    """Trader: View all available stocks for buying/selling."""
    # Note: Real implementation would connect to a market data API
    stocks_list = list(STOCKS.values())
    return render_template('available_stocks.html', title="Available Stocks", stocks=stocks_list)

@app.route('/my_portfolio')
@login_required('Trader')
def my_portfolio():
    """Trader: View detailed portfolio and transaction history."""
    user = g.user # Use the globally loaded user
    user_id = user['id']
    
    holdings_list = []
    portfolio_value = 0.0
    
    if user_id in PORTFOLIOS:
        for symbol, holding in PORTFOLIOS[user_id].items():
            stock = STOCKS.get(symbol, {'name': 'N/A', 'price': 0.0, 'industry': 'N/A'})
            current_price = stock['price']
            market_value = holding['quantity'] * current_price
            portfolio_value += market_value
            
            # Calculate average buy price correctly, handling case where it might be missing
            avg_buy_price = holding.get('avg_buy_price', 0.0)
            
            holdings_list.append({
                'symbol': symbol,
                'name': stock['name'],
                'quantity': holding['quantity'],
                'avg_buy_price': f"${avg_buy_price:,.2f}",
                'current_price': f"${current_price:,.2f}",
                'market_value': f"${market_value:,.2f}",
                'pnl': f"${(market_value - (holding['quantity'] * avg_buy_price)):,.2f}" # Simple P&L
            })

    # Only show relevant transactions for the current user
    user_transactions = [t for t in TRANSACTIONS if t['user_id'] == user_id]
    
    context = {
        'holdings': holdings_list,
        'transactions': user_transactions,
        'cash_balance': f"${user['cash_balance']:,.2f}",
        'portfolio_value': f"${portfolio_value:,.2f}"
    }
    return render_template('my_portfolio.html', title="My Portfolio", **context)


@app.route('/buy_stock/<symbol>', methods=['POST'])
@login_required('Trader')
def buy_stock(symbol):
    """Handles the stock purchase logic."""
    user = g.user # Use the globally loaded user
    user_id = user['id']
    
    try:
        quantity = int(request.form['quantity'])
        if quantity <= 0:
            flash("Quantity must be positive.", 'error')
            return redirect(url_for('available_stocks'))
    except (ValueError, TypeError):
        flash("Invalid quantity entered.", 'error')
        return redirect(url_for('available_stocks'))
        
    stock = STOCKS.get(symbol)
    if not stock:
        flash(f"Stock {symbol} not found.", 'error')
        return redirect(url_for('available_stocks'))
        
    price = stock['price']
    cost = quantity * price
    
    if user['cash_balance'] < cost:
        flash(f"Insufficient funds. Need ${cost:,.2f}, have ${user['cash_balance']:,.2f}.", 'error')
        return redirect(url_for('available_stocks'))
        
    # Process Transaction
    user['cash_balance'] -= cost
    
    # Update Portfolio
    PORTFOLIOS.setdefault(user_id, {})
    holdings = PORTFOLIOS[user_id].setdefault(symbol, {'quantity': 0, 'avg_buy_price': 0.0})
    
    # Calculate new average buy price
    old_total_cost = holdings['quantity'] * holdings['avg_buy_price']
    new_total_cost = old_total_cost + cost
    new_total_quantity = holdings['quantity'] + quantity
    
    holdings['avg_buy_price'] = new_total_cost / new_total_quantity
    holdings['quantity'] = new_total_quantity
    
    # Record Transaction
    TRANSACTIONS.append({
        'id': str(uuid.uuid4())[:8],
        'user_id': user_id,
        'username': user['username'],
        'action': 'BUY',
        'stock': symbol,
        'quantity': quantity,
        'price': price,
        'total': cost,
        'status': 'Completed',
        'date': time.strftime("%Y-%m-%d %H:%M:%S")
    })
    
    flash(f"Successfully bought {quantity} shares of {symbol} for ${cost:,.2f}.", 'success')
    return redirect(url_for('my_portfolio'))

@app.route('/sell_stock/<symbol>', methods=['POST'])
@login_required('Trader')
def sell_stock(symbol):
    """Handles the stock selling logic."""
    user = g.user # Use the globally loaded user
    user_id = user['id']
    
    try:
        quantity = int(request.form['quantity'])
        if quantity <= 0:
            flash("Quantity must be positive.", 'error')
            return redirect(url_for('my_portfolio'))
    except (ValueError, TypeError):
        flash("Invalid quantity entered.", 'error')
        return redirect(url_for('my_portfolio'))
        
    stock = STOCKS.get(symbol)
    if not stock:
        flash(f"Stock {symbol} not found.", 'error')
        return redirect(url_for('my_portfolio'))
        
    if user_id not in PORTFOLIOS or symbol not in PORTFOLIOS[user_id]:
        flash(f"You do not own any shares of {symbol}.", 'error')
        return redirect(url_for('my_portfolio'))
        
    holdings = PORTFOLIOS[user_id][symbol]
    
    if holdings['quantity'] < quantity:
        flash(f"You only own {holdings['quantity']} shares of {symbol}.", 'error')
        return redirect(url_for('my_portfolio'))
        
    # Process Transaction
    price = stock['price']
    revenue = quantity * price
    user['cash_balance'] += revenue
    
    # Update Portfolio
    holdings['quantity'] -= quantity
    
    if holdings['quantity'] == 0:
        del PORTFOLIOS[user_id][symbol]
        if not PORTFOLIOS[user_id]:
            del PORTFOLIOS[user_id]
            
    # Record Transaction
    TRANSACTIONS.append({
        'id': str(uuid.uuid4())[:8],
        'user_id': user_id,
        'username': user['username'],
        'action': 'SELL',
        'stock': symbol,
        'quantity': quantity,
        'price': price,
        'total': revenue,
        'status': 'Completed',
        'date': time.strftime("%Y-%m-%d %H:%M:%S")
    })
    
    flash(f"Successfully sold {quantity} shares of {symbol} for ${revenue:,.2f}.", 'success')
    return redirect(url_for('my_portfolio'))


if __name__ == '__main__':
    app.run(debug=True)
