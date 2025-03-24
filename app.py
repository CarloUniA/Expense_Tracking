import uuid
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import random
from datetime import datetime, date
import os
import json

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'expense_tracker_secret_key')
#app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///expenses.db')
#database_url = os.getenv('DATABASE_URL')
database_url = os.getenv('DATABASE_URL')
if database_url:
    # Fix for Render's postgres vs postgresql URL format
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Use SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

@app.template_filter('strftime')
def _strftime(value, format='%B %Y'):
    if value is None:
        return "No month selected"
    return datetime.strptime(value, '%Y-%m').strftime(format)

# Database Models
class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), unique=True, nullable=False)
    data = db.Column(db.Text, nullable=False)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    month = db.Column(db.String(7), nullable=False)
    auto_added = db.Column(db.Boolean, default=False)

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(10), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    month = db.Column(db.String(7), nullable=False)
    auto_added = db.Column(db.Boolean, default=False)

EXAMPLE_EXPENSES = [
    {"category": "Groceries", "amount": random.randint(20, 80), "date": "2025-03-01"},
    {"category": "Rent", "amount": random.randint(500, 1200), "date": "2025-03-01"},
    {"category": "Transport", "amount": random.randint(5, 30), "date": "2025-03-01"},
    {"category": "Leisure", "amount": random.randint(20, 70), "date": "2025-03-01"},
    {"category": "Dining Out", "amount": random.randint(15, 60), "date": "2025-03-01"}
]

EXPENSE_CATEGORIES = [
    "Groceries", "Transport", "Entertainment", "Bills", "Rent",
    "Dining Out", "Healthcare", "Shopping", "Utilities", "Subscriptions",
    "Education", "Travel", "Gifts", "Personal Care", "Miscellaneous"
]

EXAMPLE_INCOME = [
    {"source": "Salary", "amount": random.randint(1500, 3000), "date": "2025-03-01"},
    {"source": "Freelance", "amount": random.randint(200, 800), "date": "2025-03-01"}
]

INCOME_SOURCES = [
    "Salary", "Freelance", "Investments", "Rental", "Gifts",
    "Business", "Side Hustle", "Dividends", "Other"
]

def initialize_user_model():
    user_id = session.get('user_id', 'default_user')
    user_model_record = UserModel.query.filter_by(user_id=user_id).first()
    if not user_model_record:
        user_model = {
            "expense_categories_used": {},
            "typical_expense_amounts": {},
            "recurring_expenses": {},
            "total_expenses_per_month": {},
            "income_sources_used": {},
            "typical_income_amounts": {},
            "recurring_incomes": {},
            "total_income_per_month": {},
            "completed_months": [],
            "current_month": None,
            "budget_goal": None,
            "step": "set_goal",
            "last_active": None,
            "interactions": 0,
            "feedback": [],
            "task_metrics": {},
            "user_sentiment": []
        }
        user_model_record = UserModel(user_id=user_id, data=json.dumps(user_model))
        db.session.add(user_model_record)
        db.session.commit()
    else:
        user_model = json.loads(user_model_record.data)
    session["user_model"] = user_model
    return user_model

def save_user_model(user_model):
    user_id = session.get('user_id', 'default_user')
    user_model_record = UserModel.query.filter_by(user_id=user_id).first()
    user_model_record.data = json.dumps(user_model)
    db.session.commit()
    session["user_model"] = user_model

def update_user_model(action, data=None):
    user_model = initialize_user_model()
    current_time = datetime.now()
    user_model["last_active"] = current_time.strftime('%Y-%m-%d %H:%M:%S')
    user_model["interactions"] += 1

    if action == "set_goal":
        user_model["budget_goal"] = data["budget_goal"]
        user_model["step"] = "select_month"

    elif action == "add_expense":
        category = data["category"]
        amount = data["amount"]
        date = data["date"]
        user_model["expense_categories_used"][category] = user_model["expense_categories_used"].get(category, 0) + 1
        if category in user_model["typical_expense_amounts"]:
            prev_avg = user_model["typical_expense_amounts"][category]["avg"]
            prev_count = user_model["typical_expense_amounts"][category]["count"]
            new_avg = (prev_avg * prev_count + amount) / (prev_count + 1)
            user_model["typical_expense_amounts"][category] = {"avg": new_avg, "count": prev_count + 1}
        else:
            user_model["typical_expense_amounts"][category] = {"avg": amount, "count": 1}

    elif action == "add_income":
        source = data["source"]
        amount = data["amount"]
        date = data["date"]
        user_model["income_sources_used"][source] = user_model["income_sources_used"].get(source, 0) + 1
        if source in user_model["typical_income_amounts"]:
            prev_avg = user_model["typical_income_amounts"][source]["avg"]
            prev_count = user_model["typical_income_amounts"][source]["count"]
            new_avg = (prev_avg * prev_count + amount) / (prev_count + 1)
            user_model["typical_income_amounts"][source] = {"avg": new_avg, "count": prev_count + 1}
        else:
            user_model["typical_income_amounts"][source] = {"avg": amount, "count": 1}

    elif action == "complete_run":
        current_month = user_model["current_month"]
        user_id = session.get('user_id', 'default_user')
        expenses = Expense.query.filter_by(user_id=user_id, month=current_month).all()
        total_expenses = sum(expense.amount for expense in expenses)
        user_model["total_expenses_per_month"][current_month] = total_expenses
        incomes = Income.query.filter_by(user_id=user_id, month=current_month).all()
        total_income = sum(income.amount for income in incomes)
        user_model["total_income_per_month"][current_month] = total_income
        user_model["completed_months"].append(current_month)

        # Update recurring expenses
        expense_counts = {}
        for month in user_model["completed_months"]:
            month_expenses = Expense.query.filter_by(user_id=user_id, month=month).all()
            for expense in month_expenses:
                if expense.auto_added:
                    continue
                category = expense.category
                typical_amount = user_model["typical_expense_amounts"].get(category, {}).get("avg", expense.amount)
                key = (category, round(typical_amount, 0))
                expense_counts[key] = expense_counts.get(key, 0) + 1
        user_model["recurring_expenses"] = {
            f"{category}_{amount}": {"category": category, "amount": amount}
            for (category, amount), count in expense_counts.items() if count >= 1
        }

        # Update recurring incomes
        income_counts = {}
        for month in user_model["completed_months"]:
            month_incomes = Income.query.filter_by(user_id=user_id, month=month).all()
            for income in month_incomes:
                if income.auto_added:
                    continue
                source = income.source
                typical_amount = user_model["typical_income_amounts"].get(source, {}).get("avg", income.amount)
                key = (source, round(typical_amount, 0))
                income_counts[key] = income_counts.get(key, 0) + 1
        user_model["recurring_incomes"] = {
            f"{source}_{amount}": {"source": source, "amount": amount}
            for (source, amount), count in income_counts.items() if count >= 1
        }

        user_model["current_month"] = None
        user_model["step"] = "set_goal"

    elif action == "submit_feedback":
        feedback = data["feedback"]
        ease_of_use = data["ease_of_use"]
        satisfaction = data["satisfaction"]
        user_model["feedback"].append({"month": user_model["current_month"], "feedback": feedback})
        user_model["user_sentiment"].append({
            "month": user_model["current_month"],
            "ease_of_use": ease_of_use,
            "satisfaction": satisfaction
        })

    save_user_model(user_model)

def get_personalized_suggestions():
    user_model = initialize_user_model()
    suggestions = {}
    sorted_categories = sorted(user_model["expense_categories_used"].items(), key=lambda x: x[1], reverse=True)
    suggestions["top_categories"] = [cat[0] for cat in sorted_categories[:3]]
    suggestions["suggested_amounts"] = {cat: round(data["avg"], 2) for cat, data in user_model["typical_expense_amounts"].items()}
    suggestions["recurring_expenses"] = user_model["recurring_expenses"]
    suggestions["budget_goal"] = user_model["budget_goal"]
    sorted_income_sources = sorted(user_model["income_sources_used"].items(), key=lambda x: x[1], reverse=True)
    suggestions["top_income_sources"] = [src[0] for src in sorted_income_sources[:3]]
    suggestions["suggested_income_amounts"] = {src: round(data["avg"], 2) for src, data in user_model["typical_income_amounts"].items()}

    completed_months = user_model.get("completed_months", [])
    total_expenses_per_month = user_model.get("total_expenses_per_month", {})
    if completed_months:
        total_expenses = sum(total_expenses_per_month.get(month, 0) for month in completed_months)
        average_expenses = total_expenses / len(completed_months)
        suggested_budget_goal = round(average_expenses * 0.9, -1)
        suggestions["suggested_budget_goal"] = max(suggested_budget_goal, 100)
    else:
        suggestions["suggested_budget_goal"] = None

    return suggestions

def process_user_feedback(user_model):
    adjustments = {
        "simplify_form": False,
        "show_guidance": False
    }
    if user_model["completed_months"]:
        latest_month = user_model["completed_months"][0]
        metrics = user_model["task_metrics"].get(latest_month, {})
        time_taken = metrics.get("time_taken", 0)
        undos = metrics.get("undos", 0)
        latest_sentiment = next((s for s in user_model["user_sentiment"] if s["month"] == latest_month), None)
        ease_of_use = int(latest_sentiment["ease_of_use"]) if latest_sentiment else 3
        satisfaction = int(latest_sentiment["satisfaction"]) if latest_sentiment else 3
        if time_taken > 10 or undos > 5:
            adjustments["simplify_form"] = True
        if ease_of_use < 3 or satisfaction < 3:
            adjustments["show_guidance"] = True
    return adjustments

@app.route('/')
def home():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return render_template('home.html')

@app.route('/set_version/<version>')
def set_version(version):
    if version in ['random', 'personalized']:
        session['version'] = version
        user_id = session.get('user_id', 'default_user')
        Expense.query.filter_by(user_id=user_id).delete()
        Income.query.filter_by(user_id=user_id).delete()
        UserModel.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        if version == 'personalized':
            initialize_user_model()
        else:
            session['random_data'] = {
                "budget_goal": None,
                "current_month": None,
                "step": "set_goal",
                "completed_months": [],
                "total_expenses_per_month": {},
                "total_income_per_month": {},
                "feedback": [],
                "start_time": None
            }
            for exp in random.sample(EXAMPLE_EXPENSES, k=5):
                exp["date"] = "2025-03-01"
                expense = Expense(
                    user_id=user_id,
                    category=exp["category"],
                    amount=exp["amount"],
                    date=exp["date"],
                    description="",
                    month="2025-03"
                )
                db.session.add(expense)
            for inc in random.sample(EXAMPLE_INCOME, k=2):
                inc["date"] = "2025-03-01"
                income = Income(
                    user_id=user_id,
                    source=inc["source"],
                    amount=inc["amount"],
                    date=inc["date"],
                    description="",
                    month="2025-03"
                )
                db.session.add(income)
            db.session.commit()
        flash(f"You are now using the {version.capitalize()} version.")
    return redirect(url_for('home'))

@app.route('/track_expenses', methods=['GET', 'POST'])
def track_expenses():
    if 'version' not in session:
        flash("Please select a version first.")
        return redirect(url_for('home'))

    use_personalization = session['version'] == 'personalized'
    user_id = session.get('user_id', str(uuid.uuid4()))
    session['user_id'] = user_id
    user_model = initialize_user_model() if use_personalization else {}

    if not use_personalization:
        if 'random_data' not in session:
            session['random_data'] = {
                "budget_goal": None,
                "current_month": None,
                "step": "set_goal",
                "completed_months": [],
                "total_expenses_per_month": {},
                "total_income_per_month": {},
                "feedback": [],
                "start_time": None
            }
        random_data = session['random_data']
        if random_data.get("step") == "set_goal":
            random_budget_goal = round(random.uniform(500, 1500), -1)
            random_data["budget_goal"] = random_budget_goal
            session['random_data'] = random_data
        current_month = random_data.get("current_month")
        step = random_data.get("step", "set_goal")
        start_time = random_data.get("start_time")
    else:
        random_data = {}
        current_month = user_model.get("current_month")
        step = user_model.get("step", "set_goal")
        start_time = session.get('start_time')

    expenses = Expense.query.filter_by(user_id=user_id, month=current_month).all() if current_month else []
    incomes = Income.query.filter_by(user_id=user_id, month=current_month).all() if current_month else []
    suggestions = get_personalized_suggestions() if use_personalization else {}

    if (use_personalization and current_month and step == "track_expenses") or (
            not use_personalization and current_month and step == "track_expenses"):
        today_date = f"{current_month}-01"
    else:
        today_date = date.today().strftime("%Y-%m-%d")

    total_expenses = sum(expense.amount for expense in expenses)
    total_income = sum(income.amount for income in incomes)
    budget_goal = user_model.get("budget_goal") if use_personalization else random_data.get("budget_goal")
    budget_status = "on_track" if budget_goal is not None and (budget_goal - total_expenses) >= 0 else "over_budget"
    budget_remaining = budget_goal - total_expenses if budget_goal is not None else 0

    if use_personalization and current_month and step == "track_expenses":
        for key, rec_expense in suggestions["recurring_expenses"].items():
            new_date = f"{current_month}-01"
            if not Expense.query.filter_by(user_id=user_id, month=current_month, category=rec_expense["category"],
                                          amount=rec_expense["amount"]).first():
                new_expense = Expense(
                    user_id=user_id,
                    category=rec_expense["category"],
                    amount=rec_expense["amount"],
                    date=new_date,
                    description="Auto-added recurring expense",
                    month=current_month,
                    auto_added=True
                )
                db.session.add(new_expense)

        for key, rec_income in user_model.get("recurring_incomes", {}).items():
            new_date = f"{current_month}-01"
            if not Income.query.filter_by(user_id=user_id, month=current_month, source=rec_income["source"],
                                         amount=rec_income["amount"]).first():
                new_income = Income(
                    user_id=user_id,
                    source=rec_income["source"],
                    amount=rec_income["amount"],
                    date=new_date,
                    description="Auto-added recurring income",
                    month=current_month,
                    auto_added=True
                )
                db.session.add(new_income)

        db.session.commit()
        expenses = Expense.query.filter_by(user_id=user_id, month=current_month).all()
        incomes = Income.query.filter_by(user_id=user_id, month=current_month).all()
        total_expenses = sum(expense.amount for expense in expenses)
        total_income = sum(income.amount for income in incomes)
        budget_goal = user_model.get("budget_goal") if use_personalization else random_data.get("budget_goal")
        budget_status = "on_track" if budget_goal is not None and (budget_goal - total_expenses) >= 0 else "over_budget"
        budget_remaining = budget_goal - total_expenses if budget_goal is not None else 0

    ui_adjustments = {"simplify_form": False, "show_guidance": False}
    if use_personalization:
        ui_adjustments = process_user_feedback(user_model)

    if request.method == 'POST':
        action = request.form.get('action', '')

        # Handle the "Back" action for the Personalized version
        if action == 'go_back' and use_personalization:
            if step == 'select_month':
                user_model["step"] = "set_goal"
            elif step == 'track_expenses':
                user_model["step"] = "select_month"
                user_model["current_month"] = None  # Reset the selected month
            elif step == 'finish_run':
                user_model["step"] = "track_expenses"
            save_user_model(user_model)
            flash("Returned to the previous step.")
            return redirect(url_for('track_expenses'))

        if action == 'set_goal' and step == "set_goal":
            try:
                budget_goal = float(request.form.get('budget_goal'))
                if budget_goal <= 0:
                    flash("Budget goal must be positive.")
                else:
                    if use_personalization:
                        update_user_model("set_goal", {"budget_goal": budget_goal})
                    else:
                        random_data["budget_goal"] = budget_goal
                        random_data["step"] = "select_month"
                        session['random_data'] = random_data
                    flash("Budget goal set! Now select a month.")
            except ValueError:
                flash("Invalid budget goal. Enter a number.")
            return redirect(url_for('track_expenses'))

        elif action == 'select_month' and step == "select_month":
            selected_month = request.form.get('selected_month')
            completed_months = user_model["completed_months"] if use_personalization else random_data["completed_months"]
            if selected_month in completed_months:
                flash("Month already completed. Select a new one.")
            else:
                if use_personalization:
                    user_model["current_month"] = selected_month
                    user_model["step"] = "track_expenses"
                    user_model["task_metrics"][selected_month] = {
                        "start_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "undos": 0
                    }
                    save_user_model(user_model)
                    session['start_time'] = user_model["task_metrics"][selected_month]["start_time"]
                else:
                    random_data["current_month"] = selected_month
                    random_data["step"] = "track_expenses"
                    random_data["start_time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    Expense.query.filter_by(user_id=user_id).delete()
                    Income.query.filter_by(user_id=user_id).delete()
                    db.session.commit()
                    for exp in random.sample(EXAMPLE_EXPENSES, k=5):
                        exp["date"] = f"{selected_month}-01"
                        expense = Expense(
                            user_id=user_id,
                            category=exp["category"],
                            amount=exp["amount"],
                            date=exp["date"],
                            description="",
                            month=selected_month
                        )
                        db.session.add(expense)
                    for inc in random.sample(EXAMPLE_INCOME, k=2):
                        inc["date"] = f"{selected_month}-01"
                        income = Income(
                            user_id=user_id,
                            source=inc["source"],
                            amount=inc["amount"],
                            date=inc["date"],
                            description="",
                            month=selected_month
                        )
                        db.session.add(income)
                    db.session.commit()
                    session['random_data'] = random_data
            return redirect(url_for('track_expenses'))

        elif action == 'add_expense' and step == "track_expenses":
            category = request.form.get('expense_category')
            try:
                amount = float(request.form.get('expense_amount'))
                expense_date = request.form.get('expense_date', f"{current_month}-01")
                description = request.form.get('expense_description', '')
                new_expense = Expense(
                    user_id=user_id,
                    category=category,
                    amount=amount,
                    date=expense_date,
                    description=description,
                    month=current_month,
                    auto_added=False
                )
                db.session.add(new_expense)
                db.session.commit()
                if use_personalization:
                    update_user_model("add_expense", {
                        "category": category,
                        "amount": amount,
                        "date": expense_date,
                        "description": description
                    })
                flash("Expense added!")
            except ValueError:
                flash("Invalid amount. Enter a number.")
            return redirect(url_for('track_expenses'))

        elif action == 'delete_expense':
            expense_id = request.form.get('expense_id')
            expense = db.session.get(Expense, expense_id)
            if expense and expense.user_id == user_id:
                db.session.delete(expense)
                db.session.commit()
                if use_personalization:
                    user_model["task_metrics"][current_month]["undos"] = user_model["task_metrics"][current_month].get("undos", 0) + 1
                    save_user_model(user_model)
                flash("Expense deleted.")
            return redirect(url_for('track_expenses'))

        elif action == 'edit_expense':
            expense_id = request.form.get('expense_id')
            expense = db.session.get(Expense, expense_id)
            if expense and expense.user_id == user_id:
                try:
                    expense.category = request.form.get('expense_category')
                    expense.amount = float(request.form.get('expense_amount'))
                    expense.date = request.form.get('expense_date', expense.date)
                    expense.description = request.form.get('expense_description', expense.description)
                    db.session.commit()
                    if use_personalization:
                        update_user_model("add_expense", {
                            "category": expense.category,
                            "amount": expense.amount,
                            "date": expense.date,
                            "description": expense.description
                        })
                        user_model["task_metrics"][current_month]["undos"] = user_model["task_metrics"][current_month].get("undos", 0) + 1
                        save_user_model(user_model)
                    flash("Expense updated.")
                except ValueError:
                    flash("Invalid amount.")
            return redirect(url_for('track_expenses'))

        elif action == 'add_income' and step == "track_expenses":
            source = request.form.get('income_source')
            try:
                amount = float(request.form.get('income_amount'))
                income_date = request.form.get('income_date', f"{current_month}-01")
                description = request.form.get('income_description', '')
                new_income = Income(
                    user_id=user_id,
                    source=source,
                    amount=amount,
                    date=income_date,
                    description=description,
                    month=current_month,
                    auto_added=False
                )
                db.session.add(new_income)
                db.session.commit()
                if use_personalization:
                    update_user_model("add_income", {
                        "source": source,
                        "amount": amount,
                        "date": income_date,
                        "description": description
                    })
                flash("Income added!")
            except ValueError:
                flash("Invalid amount. Enter a number.")
            return redirect(url_for('track_expenses'))

        elif action == 'delete_income':
            income_id = request.form.get('income_id')
            income = db.session.get(Income, income_id)
            if income and income.user_id == user_id:
                db.session.delete(income)
                db.session.commit()
                if use_personalization:
                    user_model["task_metrics"][current_month]["undos"] = user_model["task_metrics"][current_month].get("undos", 0) + 1
                    save_user_model(user_model)
                flash("Income deleted.")
            return redirect(url_for('track_expenses'))

        elif action == 'edit_income':
            income_id = request.form.get('income_id')
            income = db.session.get(Income, income_id)
            if income and income.user_id == user_id:
                try:
                    income.source = request.form.get('income_source')
                    income.amount = float(request.form.get('income_amount'))
                    income.date = request.form.get('income_date', income.date)
                    income.description = request.form.get('income_description', income.description)
                    db.session.commit()
                    if use_personalization:
                        update_user_model("add_income", {
                            "source": income.source,
                            "amount": income.amount,
                            "date": income.date,
                            "description": income.description
                        })
                        user_model["task_metrics"][current_month]["undos"] = user_model["task_metrics"][current_month].get("undos", 0) + 1
                        save_user_model(user_model)
                    flash("Income updated.")
                except ValueError:
                    flash("Invalid amount.")
            return redirect(url_for('track_expenses'))

        elif action == 'verify_expenses' and step == "track_expenses":
            if expenses:
                if use_personalization:
                    user_model["step"] = "finish_run"
                    save_user_model(user_model)
                else:
                    random_data["step"] = "finish_run"
                    session['random_data'] = random_data
            else:
                flash("Add at least one expense first.")
            return redirect(url_for('track_expenses'))

        elif action == 'submit_feedback' and step == "finish_run":
            feedback = request.form.get('feedback')
            ease_of_use = request.form.get('ease_of_use')
            satisfaction = request.form.get('satisfaction')
            if use_personalization:
                start_time_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                end_time_dt = datetime.now()
                time_taken = (end_time_dt - start_time_dt).total_seconds() / 60
                user_model["task_metrics"][current_month]["time_taken"] = time_taken
                update_user_model("submit_feedback", {
                    "feedback": feedback,
                    "ease_of_use": ease_of_use,
                    "satisfaction": satisfaction
                })
                update_user_model("complete_run")
                session['start_time'] = None
            else:
                start_time_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                end_time_dt = datetime.now()
                time_taken = (end_time_dt - start_time_dt).total_seconds() / 60
                random_data["feedback"].append({
                    "month": current_month,
                    "feedback": feedback,
                    "time_taken": time_taken
                })
                random_data["total_expenses_per_month"][current_month] = total_expenses
                random_data["total_income_per_month"][current_month] = total_income
                random_data["completed_months"].append(current_month)
                random_data["current_month"] = None
                random_data["step"] = "set_goal"
                random_data["start_time"] = None
                session['random_data'] = random_data
            flash("Run completed! Start a new one.")
            return redirect(url_for('track_expenses'))

    expense_categories = EXPENSE_CATEGORIES.copy()
    if use_personalization and suggestions.get("top_categories"):
        for category in reversed(suggestions["top_categories"]):
            if category in expense_categories:
                expense_categories.remove(category)
                expense_categories.insert(0, category)

    progress_steps = [
        {"name": "Set Goal", "id": "set_goal", "completed": step != "set_goal"},
        {"name": "Select Month", "id": "select_month", "completed": step not in ["set_goal", "select_month"]},
        {"name": "Track Expenses", "id": "track_expenses",
         "completed": step not in ["set_goal", "select_month", "track_expenses"]},
        {"name": "Finish Run", "id": "finish_run", "completed": step == "set_goal" and current_month is None}
    ]

    return render_template(
        'track_expenses.html',
        expenses=expenses,
        total_expenses=total_expenses,
        expense_categories=expense_categories,
        incomes=incomes,
        total_income=total_income,
        income_sources=INCOME_SOURCES,
        budget_status=budget_status,
        budget_remaining=budget_remaining,
        today_date=today_date,
        use_personalization=use_personalization,
        suggestions=suggestions,
        user_model=user_model,
        random_data=random_data,
        current_month=current_month,
        step=step,
        progress_steps=progress_steps,
        ui_adjustments=ui_adjustments
    )

@app.route('/overview', methods=['GET', 'POST'])
def overview():
    if 'version' not in session:
        flash("Please select a version first.")
        return redirect(url_for('home'))

    use_personalization = session['version'] == 'personalized'
    user_id = session.get('user_id', 'default_user')
    user_model = initialize_user_model() if use_personalization else {}
    random_data = session.get('random_data', {}) if not use_personalization else {}

    if use_personalization:
        if user_model.get("budget_goal") is None:
            flash("Please set a budget goal first.")
            return redirect(url_for('track_expenses'))
    else:
        if random_data.get("budget_goal") is None:
            flash("Please set a budget goal first.")
            return redirect(url_for('track_expenses'))

    completed_months = user_model.get("completed_months", []) if use_personalization else random_data.get("completed_months", [])
    completed_months.sort(reverse=True)

    all_months_with_data = set()
    expenses_all = Expense.query.filter_by(user_id=user_id).all()
    incomes_all = Income.query.filter_by(user_id=user_id).all()
    for expense in expenses_all:
        all_months_with_data.add(expense.month)
    for income in incomes_all:
        all_months_with_data.add(income.month)
    all_months_with_data = sorted(list(all_months_with_data), reverse=True)

    current_month = user_model.get("current_month") if use_personalization else random_data.get("current_month")
    if current_month:
        display_month = current_month
    elif all_months_with_data:
        display_month = all_months_with_data[0]
    elif completed_months:
        display_month = completed_months[0]
    else:
        display_month = None

    if display_month:
        expenses = Expense.query.filter_by(user_id=user_id, month=display_month).all()
        incomes = Income.query.filter_by(user_id=user_id, month=display_month).all()
    else:
        expenses = []
        incomes = []

    total_expenses = sum(expense.amount for expense in expenses)
    total_income = sum(income.amount for income in incomes)
    expenses_by_category = {}
    for expense in expenses:
        expenses_by_category[expense.category] = expenses_by_category.get(expense.category, 0) + expense.amount
    incomes_by_source = {}
    for income in incomes:
        incomes_by_source[income.source] = incomes_by_source.get(income.source, 0) + income.amount

    trends = {
        "total_expenses_per_month": user_model.get("total_expenses_per_month", {}) if use_personalization else random_data.get("total_expenses_per_month", {}),
        "total_income_per_month": user_model.get("total_income_per_month", {}) if use_personalization else random_data.get("total_income W_per_month", {})
    }

    return render_template(
        'overview.html',
        expenses_by_category=expenses_by_category.items(),
        total_expenses=total_expenses,
        total_income=total_income,
        incomes_by_source=incomes_by_source.items(),
        use_personalization=use_personalization,
        user_model=user_model,
        random_data=random_data,
        current_month=display_month,
        completed_months=completed_months,
        trends=trends,
        has_data=bool(expenses or incomes)
    )

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=port, debug=True)