import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * FROM portfolios WHERE id=:id", id=session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])[0][
        "cash"
    ]
    total = cash

    for row in rows:
        stock = lookup(row["symbol"])
        row["name"] = stock["name"]
        row["price"] = usd(stock["price"])
        row["total"] = stock["price"] * row["shares"]
        total += row["total"]
        row["total"] = usd(row["total"])

    return render_template("index.html", rows=rows, cash=usd(cash), total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # user reached route via POST
    if request.method == "POST":

        # Check for symbol provided
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        symbol = request.form.get("symbol")

        # Check if symbol exists
        if not lookup(symbol):
            return apology("invalid symbol", 400)

        # Check for quantity
        if not request.form.get("shares"):
            return apology("missing # of shares", 400)

        user_id = session["user_id"]
        price = lookup(symbol)["price"]
        shares = request.form.get("shares")
        cash = db.execute("SELECT cash FROM users WHERE id=:id", id=user_id)[0]["cash"]

        # Check for enough funds
        if cash < price:
            return apology("Not enough cash", 400)

        # Log transaction information
        db.execute(
            "INSERT INTO transactions ('id', 'type', 'symbol', 'shares', 'price') VALUES(:id, 'buy', :symbol, :shares, :price)",
            id=user_id,
            symbol=symbol,
            shares=shares,
            price=usd(price),
        )

        # Deduct transaction from cash

        db.execute(
            "UPDATE users SET cash=:cash WHERE id=:id",
            cash=cash - price * int(shares),
            id=user_id,
        )

        # Get portfolio table
        inPortfolio = db.execute(
            "SELECT * FROM portfolios WHERE id=:id AND symbol=:symbol",
            id=user_id,
            symbol=symbol,
        )

        # Add stock if it is not already in portfolio
        if not inPortfolio:
            db.execute(
                "INSERT INTO portfolios ('id', 'symbol', 'shares') VALUES(:id, :symbol, :shares)",
                id=user_id,
                symbol=symbol,
                shares=shares,
            )

        # otherwise, update it with the new shares
        else:
            totalShares = inPortfolio[0]["shares"] + shares
            db.execute(
                "UPDATE portfolios SET shares=:shares WHERE id=:id AND symbol=:symbol",
                id=user_id,
                shares=totalShares,
            )

        # Redirect user to home page
        return redirect("/")

    # user reached route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    stocks = db.execute("SELECT * FROM transactions WHERE id=:id", id=session["user_id"])
    return render_template("history.html", stocks=stocks)
    


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = :username",
            username=request.form.get("username"),
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Check for symbol provided
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        # Check if symbol exists
        if not lookup(request.form.get("symbol")):
            return apology("invalid symbol", 400)

        stock = lookup(request.form.get("symbol"))
        name = stock["name"]
        price = stock["price"]
        symbol = stock["symbol"]
        year_high = stock["year_high"]
        year_low = stock["year_low"]
        change = stock["change"]
        percent_change = round(stock["change_percent"] * 100, 2)
        return render_template(
            "quoted.html",
            name=name,
            price=usd(price),
            symbol=symbol,
            year_high=usd(year_high),
            year_low=usd(year_low),
            change=usd(change),
            percent_change=percent_change,
        )

    else:
        # User reached route via GET (as by link)
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure Username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure Password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure Password Confirmation matches Password
        elif not request.form.get("confirmation"):
            return apology("passwords must match", 403)

        # Add user to database
        username = request.form.get("username")
        password_hash = generate_password_hash(request.form.get("password"))
        db.execute(
            "INSERT INTO users ('username', 'hash') VALUES(:username, :hash)",
            username=username,
            hash=password_hash,
        )

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    user_id = session["user_id"]

    # user reached route via POST
    if request.method == "POST":

        # Check for symbol provided
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        symbol = request.form.get("symbol")

        # Check for quantity
        if not request.form.get("shares"):
            return apology("missing # of shares", 400)

        shares = int(request.form.get("shares"))
        price = lookup(symbol)["price"]
        cash = db.execute("SELECT cash FROM users WHERE id=:id", id=user_id)[0]["cash"]
        current_shares = db.execute(
            "SELECT * FROM portfolios WHERE id=:id AND symbol=:symbol",
            id=user_id,
            symbol=symbol,
        )[0]["shares"]

        # Check for enough shares
        if shares > current_shares:
            return apology("Not enough shares", 400)

        # Log transaction information
        db.execute(
            "INSERT INTO transactions ('id', 'type', 'symbol', 'shares', 'price') VALUES(:id, 'sell', :symbol, :shares, :price)",
            id=user_id,
            symbol=symbol,
            shares=shares,
            price=usd(price),
        )

        # Add transaction to cash
        db.execute(
            "UPDATE users SET cash=:cash WHERE id=:id",
            cash=cash + price * shares,
            id=user_id,
        )

        # Remove from portfolio if no more shares
        if shares == current_shares:
            db.execute(
                "DELETE FROM portfolios WHERE id=:id AND symbol=:symbol",
                id=user_id,
                symbol=symbol,
            )

        # otherwise, update it with the new shares
        else:
            db.execute(
                "UPDATE portfolios SET shares=:shares WHERE id=:id AND symbol=:symbol",
                id=user_id,
                shares=current_shares - shares,
            )

        # Redirect user to home page
        return redirect("/")

    # user reached route via GET
    else:
        stocks = db.execute("SELECT symbol FROM portfolios WHERE id=:id", id=user_id)
        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
