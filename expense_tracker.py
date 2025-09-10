import streamlit as st
import json
import os

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
    people = get_all_people(expenses)
    balances = {person: 0 for person in people}

    for e in expenses:
        payer = e["payer"]

        if isinstance(e["participants"], dict):  # custom split
            for p, share in e["participants"].items():
                balances[p] -= share
            balances[payer] += e["amount"]

        else:  # equal split
            share = e["amount"] / len(e["participants"])
            for p in e["participants"]:
                balances[p] -= share
            balances[payer] += e["amount"]

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

        payment = min(debt, credit)
        settlements.append(f"{debtor} should pay {creditor} {payment:.2f}")

        debtors[i] = (debtor, debt - payment)
        creditors[j] = (creditor, credit - payment)

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    return settlements

# -------------------------------
# Streamlit UI
# -------------------------------
st.title("💰 Trip Expense Tracker")

filename = st.text_input("Enter expense file name", "trip_expenses.json")
expenses = load_expenses(filename)

# Add expense section (no form → instant re-render)
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

        expenses.append(expense)
        save_expenses(filename, expenses)
        st.success("✅ Expense added!")

# Show balances
if st.button("📊 Show Final Balances"):
    if not expenses:
        st.warning("⚠️ No expenses recorded yet.")
    else:
        balances = calculate_balances(expenses)
        
        # Add icon for Final Balances
        st.subheader("💹 Final Balances")
        for person, balance in balances.items():
            if balance > 0:
                st.write(f"🟢 **{person} should receive {balance:.2f}**")
            elif balance < 0:
                st.write(f"🔴 **{person} should pay {-balance:.2f}**")
            else:
                st.write(f"⚪ {person} is settled up.")

        # Add icon for Settlement Plan
        st.subheader("🤝 Settlement Plan")
        settlements = suggest_payments(balances)
        if settlements:
            for s in settlements:
                st.write(f"➡️ {s}")
        else:
            st.write("✅ Everyone is settled up!")
