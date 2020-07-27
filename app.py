import os
import sys

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
db = SQL("sqlite:///finance.db", connect_args={'check_same_thread': False})

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    id=session["user_id"]
    db.execute("CREATE TABLE IF NOT EXISTS current ( id INTEGER NOT NULL, symbol TEXT NOT NULL, shares INTEGER NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS history ( id INTEGER NOT NULL, action TEXT NOT NULL, symbol TEXT NOT NULL, shares INTEGER, price INTEGER, stamp TEXT)")
    owns = db.execute("SELECT * FROM current WHERE id=:id", id=id)
    looks=[]
    totals = []
    cash = int(db.execute("SELECT cash FROM users WHERE id=:id", id=id)[0]['cash'])
    sumtotal=cash
    for own in owns:
        look = lookup(own['symbol'])
        total = float(own['shares'])*float(look['price'])
        looks.append(look)
        totals.append(total)
        sumtotal = sumtotal+total
    return render_template("index.html", zips=zip(owns,looks,totals), sum=sumtotal,cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method=="GET":
        return render_template("buy.html")
    else:
        symbol=request.form['symbol']
        look = lookup(symbol)
        if not look:
            return apology("Please enter valid symbol")
        else:
            shares=float(request.form['shares'])
            price=look['price']
            name=look['name']
            id=session["user_id"]
            balance=float(db.execute("SELECT cash FROM users WHERE id=:id", id=id)[0]['cash'])
            if balance>(price*shares):
                db.execute("INSERT INTO history (id,action,symbol,shares,price,stamp) VALUES (:id, :action, :symbol, :shares, :price, datetime('now','localtime'))",id=id, action="BUY", symbol=symbol, shares=shares, price=price)
                curshares = db.execute("SELECT shares FROM current WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=symbol)
                if not curshares:
                    db.execute("INSERT INTO current (id, symbol, shares) VALUES (:id, :symbol, :shares)", id=id, symbol=symbol, shares=shares)
                else:
                    curshares = int(curshares[0]['shares'])
                    curshares = curshares+shares
                    db.execute("UPDATE current SET shares=:curshares WHERE id=:id AND symbol=:symbol", curshares=curshares, id=id, symbol=symbol)
                balance = str(balance-(shares*price))
                db.execute("UPDATE users SET cash=:balance WHERE id=:id", balance=balance, id=session["user_id"])
                return redirect("/")
            else:
                return apology("Transaction Failed")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    id=session["user_id"]
    histories = db.execute("SELECT * FROM history WHERE id=:id ORDER BY stamp DESC", id=id)
    return render_template("history.html", histories=histories)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    if request.method=="GET":
        return render_template("quote.html")
    else:
        quote = lookup(request.form.get("symbol"))
        print(quote, file=sys.stderr)
        if quote==None:
            return apology("Quote Failed")
        else:
            return render_template('quoted.html', quote=quote)



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method=="GET":
        return render_template("register.html")
    else:
        username = request.form['username']
        if not username:
            return apology("Must enter username!")
        password = request.form['password']
        if not password:
            return apology("Must enter password!")
        phash = generate_password_hash(password)
        rows = db.execute("INSERT INTO users (username,hash) VALUES (:username, :phash)", username=username, phash=phash)
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    id=session["user_id"]
    options = db.execute("SELECT * FROM current WHERE id=:id", id=id)
    if request.method=="GET":
        return render_template("sell.html", options=options)
    else:
        symbol=request.form['symbol']
        shares=int(request.form['shares'])
        curshares=int(db.execute("SELECT shares FROM current WHERE id=:id AND symbol=:symbol", id=id, symbol=symbol)[0]['shares'])
        if shares<=curshares:
            curshares=curshares-shares
            if curshares==0:
                db.execute("DELETE FROM current WHERE id=:id AND symbol=:symbol", id=id, symbol=symbol)
            else:
                db.execute("UPDATE current SET shares=:curshares WHERE id=:id AND symbol=:symbol",curshares=curshares, id=id, symbol=symbol)
            price=float(lookup(symbol)['price'])
            rate=price*shares
            cash=float(db.execute("SELECT cash FROM users WHERE id=:id", id=id)[0]['cash'])
            cash = cash+rate
            db.execute("UPDATE users SET cash=:cash WHERE id=:id", cash=cash, id=id)
            db.execute("INSERT INTO history (id, action, symbol, shares, price, stamp) VALUES (:id, :action, :symbol, :shares, :price, datetime('now', 'localtime'))", id=id, action="SELL", symbol=symbol, shares=shares, price=price)
            return redirect("/")
        else:
            return apology("Selling more than Owned")
        return apology("else reached")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
