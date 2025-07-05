from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os

app = Flask(__name__)
app.secret_key = "stocker_secret_2024"

# Database config
basedir = os.path.abspath(os.path.dirname(__file__))
# Check if db directory exists, if not create it
db_dir = os.path.join(basedir, 'db')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

db_path = os.path.join(db_dir, 'stocker.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Add a print statement to debug
print(f"Connecting to database at: {db_path}")

db = SQLAlchemy(app)


# ------------------- Models ------------------- #

class User(db.Model):
    __tablename__ = 'user'  # Explicitly set table name to match the database
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'admin' or 'trader'
    # Relationships
    transaction = db.relationship('Transaction', backref='user', lazy=True)
    portfolio = db.relationship('Portfolio', backref='user', lazy=True)

class Stock(db.Model):
    __tablename__ = 'stock'  # Explicitly set table name to match the database
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    market_cap = db.Column(db.Float, nullable=False)
    sector = db.Column(db.String(100), nullable=False)
    industry = db.Column(db.String(100), nullable=False)
    date_added = db.Column(db.Date, server_default=db.func.current_date())
    # Relationships
    transaction = db.relationship('Transaction', backref='stock', lazy=True)
    portfolio = db.relationship('Portfolio', backref='stock', lazy=True)

class Transaction(db.Model):
    __tablename__ = 'stock_transaction'  # Explicitly set table name to match the database
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    action = db.Column(db.String(10), nullable=False)  # 'buy' or 'sell'
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(10), nullable=False, default='completed')  # 'pending', 'completed', 'failed'
    transaction_date = db.Column(db.DateTime, server_default=db.func.now())

class Portfolio(db.Model):
    __tablename__ = 'portfolio'  # Explicitly set table name to match the database
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    average_price = db.Column(db.Float, nullable=False)

# ------------------- Routes ------------------- #
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email, role=role).first()
        print(f"Trying to login with: {email} ({role})")

        if user and user.password == password:
            print("Login successful!")
            session['email'] = user.email
            session['role'] = user.role
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard_admin' if role == 'admin' else 'dashboard_trader'))
        else:
            print("Login failed.")
            flash('Invalid credentials or role mismatch.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('User already exists. Please login.', 'warning')
            return redirect(url_for('login'))

        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash(f"Account created for {username}", 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/dashboard_admin')
def dashboard_admin():
    if 'email' not in session or session.get('role') != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('login'))

    user = User.query.filter_by(email=session['email']).first()
    stocks = Stock.query.all()
    return render_template('dashboard_admin.html', user=user, market_data=stocks)


@app.route('/dashboard_trader')
def dashboard_trader():
    if 'email' not in session or session.get('role') != 'trader':
        flash("Access denied. Traders only.", "danger")
        return redirect(url_for('login'))

    user = User.query.filter_by(email=session['email']).first()
    stocks = Stock.query.all()
    return render_template('dashboard_trader.html', user=user, market_data=stocks)

@app.route('/service01')
def service01():
    if 'email' not in session or session.get('role') != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('login'))
        
    traders = User.query.filter_by(role='trader').all()
    
    # Calculate portfolio values for each trader
    for trader in traders:
        trader_portfolio = Portfolio.query.filter_by(user_id=trader.id).all()
        portfolio_value = 0
        for item in trader_portfolio:
            stock = Stock.query.get(item.stock_id)
            portfolio_value += item.quantity * stock.price
        # Add this as an attribute to the trader object
        trader.total_portfolio_value = portfolio_value
    
    return render_template('service-details-1.html', traders=traders)   


@app.route('/delete_trader/<int:trader_id>', methods=['POST'])
def delete_trader(trader_id): 
    trader = User.query.get_or_404(trader_id)

    # Delete the trader
    db.session.delete(trader)
    db.session.commit()

    return redirect(url_for('service01'))


@app.route('/service02')
def service02():
    if 'email' not in session or session.get('role') != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('login'))
        
    # Join Transaction with User and Stock to get all necessary information
    transactions = (
        Transaction.query
        .join(User, Transaction.user_id == User.id)
        .join(Stock, Transaction.stock_id == Stock.id)
        .all()
    )
    return render_template('service-details-2.html', transactions=transactions)


@app.route('/service03')
def service03():
    if 'email' not in session or session.get('role') != 'admin':
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for('login'))
        
    # Join Portfolio with User and Stock to get all necessary data
    portfolios = (
        Portfolio.query
        .join(User, Portfolio.user_id == User.id)
        .join(Stock, Portfolio.stock_id == Stock.id)
        .all()
    )
    
    # Calculate total portfolio value here
    total_portfolio_value = 0
    for portfolio in portfolios:
        # Get the stock directly if needed
        stock = Stock.query.get(portfolio.stock_id)
        total_portfolio_value += portfolio.quantity * stock.price
    
    return render_template('service-details-3.html', 
                          portfolios=portfolios, 
                          total_portfolio_value=total_portfolio_value)


@app.route('/service04')
def service04():
    if 'email' not in session or session.get('role') != 'trader':
        flash("Access denied. Traders only.", "danger")
        return redirect(url_for('login'))
    
    user = User.query.filter_by(email=session['email']).first()
    stocks = Stock.query.all()
    return render_template('service-details-4.html', user=user, stocks=stocks)

@app.route('/service04/buy_stock/<int:stock_id>', methods=['GET', 'POST'])
def buy_stock(stock_id):
    if 'email' not in session or session.get('role') != 'trader':
        flash("Access denied. Traders only.", "danger")
        return redirect(url_for('login'))
    
    user = User.query.filter_by(email=session['email']).first()
    stock = Stock.query.get_or_404(stock_id)
    
    if request.method == 'POST':
        quantity = int(request.form.get('quantity', 0))
        
        if quantity <= 0:
            flash("Please enter a valid quantity.", "danger")
            return redirect(url_for('buy_stock', stock_id=stock_id))
            
        # Create transaction record
        transaction = Transaction(
            user_id=user.id,
            stock_id=stock.id,
            action='buy',
            quantity=quantity,
            price=stock.price,
            status='completed'
        )
        
        # Update or create portfolio entry
        portfolio_entry = Portfolio.query.filter_by(
            user_id=user.id, 
            stock_id=stock.id
        ).first()
        
        if portfolio_entry:
            # Update existing portfolio entry
            total_value = (portfolio_entry.quantity * portfolio_entry.average_price) + (quantity * stock.price)
            total_quantity = portfolio_entry.quantity + quantity
            portfolio_entry.quantity = total_quantity
            portfolio_entry.average_price = total_value / total_quantity
        else:
            # Create new portfolio entry
            portfolio_entry = Portfolio(
                user_id=user.id,
                stock_id=stock.id,
                quantity=quantity,
                average_price=stock.price
            )
            db.session.add(portfolio_entry)
        
        # Commit all changes
        db.session.add(transaction)
        db.session.commit()
        
        flash(f"Successfully purchased {quantity} shares of {stock.symbol}!", "success")
        return redirect(url_for('service05'))
    
    return render_template('buy_stock.html', user=user, stock=stock)

@app.route('/service04/sell_stock/<int:stock_id>', methods=['GET', 'POST'])
def sell_stock(stock_id):
    if 'email' not in session or session.get('role') != 'trader':
        flash("Access denied. Traders only.", "danger")
        return redirect(url_for('login'))
    
    user = User.query.filter_by(email=session['email']).first()
    stock = Stock.query.get_or_404(stock_id)
    
    # Check if user owns this stock
    portfolio_entry = Portfolio.query.filter_by(
        user_id=user.id, 
        stock_id=stock.id
    ).first()
    
    if not portfolio_entry:
        flash("You don't own any shares of this stock.", "danger")
        return redirect(url_for('service04'))
    
    if request.method == 'POST':
        quantity = int(request.form.get('quantity', 0))
        
        if quantity <= 0:
            flash("Please enter a valid quantity.", "danger")
            return redirect(url_for('sell_stock', stock_id=stock_id))
            
        if quantity > portfolio_entry.quantity:
            flash("You don't have enough shares to sell.", "danger")
            return redirect(url_for('sell_stock', stock_id=stock_id))
        
        # Create transaction record
        transaction = Transaction(
            user_id=user.id,
            stock_id=stock.id,
            action='sell',
            quantity=quantity,
            price=stock.price,
            status='completed'
        )
        
        # Update portfolio entry
        portfolio_entry.quantity -= quantity
        
        # If all shares are sold, remove the portfolio entry
        if portfolio_entry.quantity == 0:
            db.session.delete(portfolio_entry)
        
        # Commit all changes
        db.session.add(transaction)
        db.session.commit()
        
        flash(f"Successfully sold {quantity} shares of {stock.symbol}!", "success")
        return redirect(url_for('service05'))
    
    return render_template('sell_stock.html', user=user, stock=stock, portfolio_entry=portfolio_entry)

# Portfolio view for traders
@app.route('/service05')
def service05():
    if 'email' not in session or session.get('role') != 'trader':
        flash("Access denied. Traders only.", "danger")
        return redirect(url_for('login'))
    
    user = User.query.filter_by(email=session['email']).first()
    
    # Get portfolio with stock details
    portfolio = (
        Portfolio.query
        .filter_by(user_id=user.id)
        .join(Stock, Portfolio.stock_id == Stock.id)
        .all()
    )
    
    # Calculate total portfolio value
    total_value = sum(item.quantity * item.stock.price for item in portfolio)
    
    # Get transaction history
    transactions = (
        Transaction.query
        .filter_by(user_id=user.id)
        .join(Stock, Transaction.stock_id == Stock.id)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )
    
    return render_template('service-details-5.html', user=user, portfolio=portfolio, total_value=total_value, transactions=transactions)

######## Debugging route to check if stocks are accessible
@app.route('/debug/check_stocks')
def check_stocks():
    # This route will check if stocks are accessible in the database
    try:
        stocks = Stock.query.all()
        result = {
            "success": True,
            "stocks_count": len(stocks),
            "first_five": [{"id": s.id, "symbol": s.symbol, "name": s.name, "price": s.price} for s in stocks[:5]]
        }
    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
    
    # Return as plain text for easy debugging
    return "<pre>" + str(result) + "</pre>"
##############

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True) 

