import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
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
    USER = session["user_id"]

    stockUser = db.execute("SELECT symbol, shares FROM stocks WHERE id_user = ?", USER)

    stockDicUser = []
    cashStock = 0

    for stocks in stockUser:
        data = lookup(stocks['symbol'])
        data['shares'] = stocks['shares']
        stockDicUser.append(data)
        cashStock += data['price'] * stocks['shares']

    cash = db.execute("SELECT * FROM users WHERE id = ?", USER)[0]['cash']

    return render_template("index.html", stockUser=stockDicUser, cash=cash, total=cashStock)

    # return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    USER = session["user_id"]

    if request.method == "GET":
        return render_template("buy.html")

    elif request.method == "POST":

        symbol = request.form.get("symbol")
        data = lookup(symbol)

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("shares must be a positive integer")

        # Verificando symbol

        if not symbol or not data:
            return apology("Stock invalid")

        # Verificando se quantidade é int
        elif int(shares) <= 0:
            return apology("Amount shares invalid")

        else:
            # Definindo função de compra

            def buyStock(symbol, amount):

                # Pegando quantidade de dinheiro do user
                cash = db.execute("SELECT * FROM users WHERE id = ?", USER)[0]['cash']
                data = lookup(symbol)

                price = data['price']
                stock = data['symbol']

                total_coast = price * amount

                # Verificando se compra é possivel
                if total_coast > cash:
                    return apology("Not enought cash")

                # Verificando se ação foi comprada anteriormente

                stockExists = db.execute("SELECT * FROM stocks WHERE id_user = ? AND symbol = ?", USER, stock)

                if stockExists:
                    # Atualizando tabela de ações
                    db.execute("UPDATE stocks SET shares = shares + ? WHERE id_user = ? AND symbol = ?", amount, USER, stock)

                    # Inserindo na tabela de transações
                    db.execute("INSERT INTO history (id_stock, id_user, shares, price) VALUES(?, ?, ?, ?)",
                             stockExists[0]['id'], USER, shares, price)

                    # Atualizando dinheiro restante
                    db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - total_coast, USER)

                # Se ação ainda não foi comprada
                else:
                    id_stock = db.execute("INSERT INTO stocks (symbol, shares, id_user) VALUES(?, ?, ?)", stock, amount, USER)

                    db.execute("INSERT INTO history (id_stock, id_user, shares, price) VALUES(?, ?, ?, ?)",
                             id_stock, USER, shares, price)

                    db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - total_coast, USER)

            buyStock(symbol, shares)
            flash("Bought!")
            return redirect("/")


@app.route("/history")
@login_required
def history():
    USER = session["user_id"]

    listStocks = db.execute(
        "SELECT stocks.symbol, history.shares, history.created_at FROM stocks INNER JOIN history ON history.id_stock = stocks.id WHERE stocks.id_user = ?", USER)

    return render_template("history.html", listStocks=listStocks)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    # """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    elif request.method == "POST":

        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Invalid Stock")

        data = lookup(symbol)

        if not data:
            return apology("Invalid Stock")

        return render_template("quoted.html", quote=data)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    elif request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        repassword = request.form.get("confirmation")

        # Verificando username e senha

        userExists = db.execute("SELECT username FROM users WHERE username = ?", username)

        print(userExists)

        if len(userExists) != 0 or not username or not password or password != repassword:
            return apology("username/password incorrect")
        else:
            password_hash = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, password_hash)
            return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    USER = session["user_id"]

    if request.method == "GET":
        listStocks = db.execute("SELECT symbol FROM stocks WHERE id_user = ?", USER)
        return render_template("sell.html", listStocks=listStocks)

    elif request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        cash = db.execute("SELECT * FROM users WHERE id = ?", USER)[0]['cash']
        data = lookup(symbol)

        price = data['price']
        stock = data['symbol']

        total_coast = price * shares

        sharesAvailable = db.execute("SELECT shares FROM stocks WHERE id_user = ? AND symbol = ?", USER, symbol)[0]['shares']

        if not symbol:
            return apology("Invalid Stock")
        if shares > sharesAvailable:
            return apology("You do not have this amount")

        stockExists = db.execute("SELECT * FROM stocks WHERE id_user = ? AND symbol = ?", USER, stock)

        if not stockExists:
            return apology("You do not have this stock")

        db.execute("UPDATE stocks SET shares = shares - ? WHERE id_user = ? AND symbol = ?", shares, USER, stock)

        # Inserindo na tabela de transações
        db.execute("INSERT INTO history (id_stock, id_user, shares, price) VALUES(?, ?, ?, ?)",
                 stockExists[0]['id'], USER, -shares, price)

        # Atualizando dinheiro restante
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + total_coast, USER)

        flash("Sold!")
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
