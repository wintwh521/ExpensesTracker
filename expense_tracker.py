import streamlit as st
import json
import os
import pandas as pd

# -------------------------------
# File Handling
# -------------------------------
def load_expenses(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return []

def save_expenses(filename, expenses):
    with open(filename, "w") as f:
        json.dump(expenses, f, indent=4)

# -------------------------------
# Expense Logic
# -------------------------------
def get_all_people(expenses):
    people = set()
    for e in expenses:
        people.add(e["payer"])
        if isinstance(e["participants"], dict):
            people.update(e["participants"].keys())
        elif isinstance(e["participants"], list):
            people.update(e["participants"])
    return list(people)

def calculate_balances(expenses):
    """Calculate net balances after sanitizing expenses (supports list or dict participants)."""
    expenses = sanitize_all(expenses)  # ensure data is normalized
    people = get_all_people(expenses)
    balances = {person: 0 for person in people}

    for e in expenses:
        payer = e["payer"]
        amount = float(e.get("amount", 0) or 0)
        participants = e["participants"]

        if isinstance(participants, dict):
            # participants already normalized to absolute shares summing to amount
            for p, share in participants.items():
                balances[p] = balances.get(p, 0.0) - float(share)
            balances[payer] = balances.get(payer, 0.0) + amount
        else:  # list -> equal split
            if len(participants) == 0:
                balances[payer] = balances.get(payer, 0.0) + amount
            else:
                share = float(amount) / len(participants)
                for p in participants:
                    balances[p] = balances.get(p, 0.0) - share
                balances[payer] = balances.get(payer, 0.0) + amount

    # round small floats
    for k in list(balances.keys()):
        balances[k] = round(balances[k], 2)
        if abs(balances[k]) < 0.01:
            balances[k] = 0.0
    return balances


def suggest_payments(balances):
    creditors = [(p, amt) for p, amt in balances.items() if amt > 0]
    debtors = [(p, -amt) for p, amt in balances.items() if amt < 0]

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    settlements = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor, debt = debtors[i]
        creditor, credit = creditors[j]
        if debtor == creditor:
            if debt > credit:
                j += 1
            else:
                i += 1
            continue
        payment = round(min(debt, credit), 2)
        if payment < 0.01:
            if debt <= credit:
                i += 1
            else:
                j += 1
            continue
        settlements.append((debtor, creditor, payment))
        debtors[i] = (debtor, round(debt - payment, 2))
        creditors[j] = (creditor, round(credit - payment, 2))
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return settlements


# -------------------------------
# Sanitize helpers
# -------------------------------
def sanitize_expense(e):
    payer = str(e.get("payer", "")).strip()
    amount = float(e.get("amount", 0) or 0)
    participants = e.get("participants", [])
    e["payer"] = payer

    if isinstance(participants, list):
        cleaned = [p.strip() for p in participants if p and str(p).strip()]
        e["participants"] = cleaned
    elif isinstance(participants, dict):
        cleaned = {}
        for k, v in participants.items():
            name = str(k).strip()
            try:
                share = float(v)
            except Exception:
                share = 0.0
            if name:
                cleaned[name] = share
        total = sum(cleaned.values())
        if total == 0 and cleaned:
            per = round(amount / len(cleaned), 2)
            cleaned = {n: per for n in cleaned.keys()}
        elif abs(total - amount) > 0.01 and total > 0:
            factor = amount / total
            cleaned = {n: round(s * factor, 2) for n, s in cleaned.items()}
            scaled_sum = sum(cleaned.values())
            diff = round(amount - scaled_sum, 2)
            if abs(diff) >= 0.01:
                first_key = next(iter(cleaned.keys()))
                cleaned[first_key] = round(cleaned[first_key] + diff, 2)
        e["participants"] = cleaned
    else:
        e["participants"] = []
    return e


def sanitize_all(expenses):
    cleaned = []
    for e in expenses:
        try:
            cleaned.append(sanitize_expense(e.copy()))
        except Exception:
            continue
    return cleaned


# -------------------------------
# Danger zone
# -------------------------------
def clear_expenses(filename):
    with open(filename, "w") as f:
        json.dump([], f, indent=4)


# -------------------------------
# Streamlit UI
# -------------------------------
st.title("💰 Trip Expense Tracker")

filename = st.text_input("Enter expense file name", "trip_expenses.json")

# --- persistent session ---
if "expenses" not in st.session_state:
    st.session_state.expenses = load_expenses(filename)
else:
    # re-sync with file on filename change
    if os.path.exists(filename):
        st.session_state.expenses = load_expenses(filename)

expenses = st.session_state.expenses

# 🔼 Upload JSON
uploaded_file = st.file_uploader("Upload an existing expenses JSON", type=["json"])
if uploaded_file is not None:
    expenses = json.load(uploaded_file)
    save_expenses(filename, expenses)
    st.session_state.expenses = expenses
    st.success("✅ Expenses loaded from uploaded file!")

# ➕ Add expense section
st.subheader("➕ Add Expense")
payer = st.text_input("Who paid?")
amount = st.number_input("How much?", min_value=0.0, format="%.2f")
description = st.text_input("Description?")
split_type = st.radio("Split type", ["Equal", "Custom"])

participants = {}
participants_list = []

if split_type == "Equal":
    participants_list = st.text_input("Participants (comma separated)").split(",")
    participants_list = [p.strip() for p in participants_list if p.strip()]
else:
    num_custom = st.number_input("How many participants?", min_value=1, step=1)
    for i in range(int(num_custom)):
        name = st.text_input(f"Participant {i+1} name", key=f"name_{i}")
        share = st.number_input(f"Amount for {name or f'P{i+1}'}", min_value=0.0, format="%.2f", key=f"share_{i}")
        if name:
            participants[name] = share

if st.button("Add Expense"):
    if payer and amount > 0:
        if split_type == "Equal":
            expense = {"payer": payer, "amount": amount, "description": description, "participants": participants_list}
        else:
            expense = {"payer": payer, "amount": amount, "description": description, "participants": participants}

        st.session_state.expenses.append(expense)
        save_expenses(filename, st.session_state.expenses)
        st.success("✅ Expense added!")

# 📊 Show balances
if st.button("📊 Show Final Balances"):
    if not expenses:
        st.warning("⚠️ No expenses recorded yet.")
    else:
        balances = calculate_balances(expenses)
        total_spent = sum(float(e["amount"]) for e in expenses)

        st.subheader(f"💵 Total Expenses: {total_spent:.2f}")

        st.subheader("💹 Final Balances")
        for person, balance in balances.items():
            if balance > 0:
                st.write(f"🟢 **{person} should receive {balance:.2f}**")
            elif balance < 0:
                st.write(f"🔴 **{person} should pay {-balance:.2f}**")
            else:
                st.write(f"⚪ {person} is settled up.")

        st.subheader("🤝 Settlement Plan")
        settlements = suggest_payments(balances)
        if settlements:
            for debtor, creditor, payment in settlements:
                st.markdown(f"➡️ **{debtor} → {creditor}: {payment:.2f}**")
        else:
            st.write("✅ Everyone is settled up!")

# 🔽 Download JSON / CSV
st.download_button(
    label="💾 Download expenses JSON",
    data=json.dumps(st.session_state.expenses, indent=4),
    file_name=filename if filename.endswith(".json") else filename + ".json",
    mime="application/json"
)

if st.session_state.expenses:
    df = pd.DataFrame(st.session_state.expenses)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📄 Download as CSV", csv, "expenses.csv", "text/csv")

# -------------------------------
# Clear Expenses with confirmation
# -------------------------------
st.markdown("---")
st.subheader("⚠️ Danger Zone")
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

# Show the clear confirmation if triggered
if st.session_state.confirm_clear:
    st.warning("Are you sure you want to clear ALL expenses? This action cannot be undone.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, clear everything"):
            clear_expenses(filename)                   # clear JSON file
            st.session_state.expenses = []             # clear in-memory list
            st.session_state.cleared = True            # flag success
            st.session_state.confirm_clear = False
            st.rerun()
    with col2:
        if st.button("❌ Cancel"):
            st.session_state.confirm_clear = False
            st.rerun()
else:
    if st.button("🗑️ Clear All Expenses"):
        st.session_state.confirm_clear = True

# Show success message after rerun (once)
if st.session_state.get("cleared", False):
    st.success("✅ All expenses cleared!")
    st.session_state.cleared = False

