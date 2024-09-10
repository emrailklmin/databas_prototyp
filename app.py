from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
import pyodbc
import pickle
from credentials_public import SQL_SERVER  # Import hidden credentials

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for flash messages

# Database connection settings using credentials from the hidden file
connection_string = f'Driver={SQL_SERVER["driver"]};Server=tcp:{SQL_SERVER["server"]},1433;Database={SQL_SERVER["database"]};Uid={SQL_SERVER["username"]};Pwd={SQL_SERVER["password"]};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'

def get_db_connection():
    conn = pyodbc.connect(connection_string)
    return conn

# Create a table for storing user data
conn_create_table = get_db_connection()
cursor = conn_create_table.cursor()
create_table_query = """
    IF NOT EXISTS (
        SELECT * FROM sys.tables WHERE name = 'financeapp_prototype'
    )
    BEGIN
        CREATE TABLE financeapp_prototype (
            username NVARCHAR(100) PRIMARY KEY,
            password NVARCHAR(255),
            income VARBINARY(MAX),
            cost VARBINARY(MAX),
            savings VARBINARY(MAX)
        )
    END
    """
cursor.execute(create_table_query)
conn_create_table.commit()
conn_create_table.close()

incomes = {}
expenses = {}
savings = {}

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    session.clear()  # Clear the session when the user visits the login page
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Check if the user exists in the database
            query = "SELECT * FROM financeapp WHERE username = ? AND password = ?"
            cursor.execute(query, (username, password))
            user = cursor.fetchone()

            if user:
                session['username'] = username  # Store the username in the session
                return redirect(url_for('finance'))  # Redirect to the finance page after successful login
            else:
                flash("Invalid username or password.")  # Flash the error message
        except Exception as e:
            flash(f"An error occurred: {e}")  # Flash any exceptions as error messages
        finally:
            conn.close()

    return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('login'))



@app.route('/register', methods=['GET', 'POST'])
def register():
    session.clear()  # Clear the session when the user visits the register page
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Check if the user already exists
            query = "SELECT * FROM financeapp WHERE username = ?"
            cursor.execute(query, (username,))
            user = cursor.fetchone()

            if user:
                flash("User already exists. Please login.", 'error')
            else:
                # Insert new user into the database
                insert_query = "INSERT INTO financeapp (username, password) VALUES (?, ?)"
                cursor.execute(insert_query, (username, password))
                conn.commit()
                flash("Registration successful! Please log in.", 'success')
                return redirect(url_for('login'))  # Redirect to login page on success
        except Exception as e:
            flash(f"An error occurred: {e}", 'error')
        finally:
            conn.close()

    # Always return the template at the end of the function
    return render_template('register.html')


@app.route('/finance', methods=['GET', 'POST'])
def finance():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Default empty dictionaries
    incomes = {}
    expenses = {}
    savings = {}

    # Handle GET request: Retrieve and display financial data
    if request.method == 'GET':
        username = session.get('username')
        if not username:
            flash("You must be logged in to access this page.")
            return redirect(url_for('login'))

        # Retrieve the finance data for the logged-in user
        query = "SELECT income, cost, savings FROM financeapp WHERE username = ?"
        cursor.execute(query, (username,))
        result = cursor.fetchone()

        if result:
            incomes = pickle.loads(result[0]) if result[0] else {}
            expenses = pickle.loads(result[1]) if result[1] else {}
            savings = pickle.loads(result[2]) if result[2] else {}

        # Calculate the totals
        total_income = sum(incomes.values())
        total_expenses = sum(expenses.values())
        total_savings = sum(savings.values())
        net_result = total_income - total_expenses
        net_result_after_savings = net_result - total_savings

        # Format the totals with spaces for thousands separator
        total_income = "{:,.0f}".format(total_income).replace(',', ' ')
        total_expenses = "{:,.0f}".format(total_expenses).replace(',', ' ')
        total_savings = "{:,.0f}".format(total_savings).replace(',', ' ')
        net_result = "{:,.0f}".format(net_result).replace(',', ' ')
        net_result_after_savings = "{:,.0f}".format(net_result_after_savings).replace(',', ' ')

        # Close the connection after data retrieval
        conn.close()

        # Render the finance page with the retrieved data
        return render_template('finance.html', 
                               incomes=incomes, 
                               expenses=expenses, 
                               savings=savings,
                               total_income=total_income, 
                               total_expenses=total_expenses, 
                               total_savings=total_savings, 
                               net_result=net_result, 
                               net_result_after_savings=net_result_after_savings)

    # Handle POST request: When the form is submitted to add new data
    if request.method == 'POST':
        username = session.get('username')
        if not username:
            flash("You must be logged in to add data.")
            return redirect(url_for('login'))

        # Retrieve form data
        type_of_entry = request.form.get('type')
        description = request.form.get('description')
        amount = request.form.get('amount')

        if not amount:
            flash("Amount is required.")
            return redirect(url_for('finance'))

        try:
            amount = float(amount)
            if amount < 0:
                flash("Amount cannot be negative.")
                return redirect(url_for('finance'))
        except ValueError:
            flash("Invalid amount. Please enter a valid number.")
            return redirect(url_for('finance'))

        # Retrieve existing data for the logged-in user
        query = "SELECT income, cost, savings FROM financeapp WHERE username = ?"
        cursor.execute(query, (username,))
        result = cursor.fetchone()

        if result:
            incomes = pickle.loads(result[0]) if result[0] else {}
            expenses = pickle.loads(result[1]) if result[1] else {}
            savings = pickle.loads(result[2]) if result[2] else {}

        # Append the new data based on the type of entry
        if type_of_entry == 'Income':
            incomes[description] = amount
        elif type_of_entry == 'Expense':
            expenses[description] = amount
        elif type_of_entry == 'Savings':
            savings[description] = amount

        # Save the updated data back to the database
        update_query = """
            UPDATE financeapp 
            SET income = ?, cost = ?, savings = ? 
            WHERE username = ?
        """
        cursor.execute(update_query, (
            pickle.dumps(incomes),  # Serialize incomes
            pickle.dumps(expenses),  # Serialize expenses
            pickle.dumps(savings),  # Serialize savings
            username
        ))
        conn.commit()

        # After form submission, redirect back to the finance page (GET request)
        return redirect(url_for('finance'))

@app.route('/delete_entry', methods=['POST'])
def delete_entry():
    username = session.get('username')
    if not username:
        flash("You must be logged in to delete data.")
        return redirect(url_for('login'))

    # Retrieve form data
    type_of_entry = request.form.get('type')
    description = request.form.get('description')

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Retrieve existing data for the logged-in user
    query = "SELECT income, cost, savings FROM financeapp WHERE username = ?"
    cursor.execute(query, (username,))
    result = cursor.fetchone()

    if result:
        incomes = pickle.loads(result[0]) if result[0] else {}
        expenses = pickle.loads(result[1]) if result[1] else {}
        savings = pickle.loads(result[2]) if result[2] else {}

    # Remove the data based on the type of entry
    if type_of_entry == 'Income':
        if description in incomes:
            del incomes[description]
    elif type_of_entry == 'Expense':
        if description in expenses:
            del expenses[description]
    elif type_of_entry == 'Savings':
        if description in savings:
            del savings[description]

    # Save the updated data back to the database
    update_query = """
        UPDATE financeapp 
        SET income = ?, cost = ?, savings = ? 
        WHERE username = ?
    """
    cursor.execute(update_query, (
        pickle.dumps(incomes),  # Serialize incomes
        pickle.dumps(expenses),  # Serialize expenses
        pickle.dumps(savings),  # Serialize savings
        username
    ))
    conn.commit()
    conn.close()

    # Redirect back to the finance page
    return redirect(url_for('finance'))


# @app.route('/finance', methods=['GET', 'POST'])
# def finance():
#     global incomes, expenses, savings
    
#     # Handle form submission
#     if request.method == 'POST':
#         type_of_entry = request.form['Type']
#         description = request.form['Description']
#         amount = float(request.form['Amount'])

#         # Add to the appropriate dictionary
#         if type_of_entry == 'income':
#             incomes[description] = amount
#         elif type_of_entry == 'expense':
#             expenses[description] = amount
#         elif type_of_entry == 'savings':
#             savings[description] = amount

#     # Calculate total income and expenses
#     total_income = sum(incomes.values())
#     total_expenses = sum(expenses.values())
#     total_savings = sum(savings.values())
#     net_result = total_income - total_expenses
#     net_result_after_savings = net_result - total_savings

#     return render_template('finance.html', incomes=incomes, expenses=expenses, savings=savings, total_income=total_income, total_expenses=total_expenses, total_savings=total_savings, net_result=net_result, net_result_after_savings=net_result_after_savings)

if __name__ == '__main__':
    # Run the app on port 8000
    app.run(host='0.0.0.0', port=8000, debug=True)
