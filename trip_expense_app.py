"""
Author: Subramanian Karunanithi
Date: 2025-04-16
Description: This script is a Streamlit-based application for managing trip expenses.
             It allows users to record advances, expenses, settlements, and generate
             summaries in JSON and PDF formats.
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime
from collections import defaultdict
from fpdf import FPDF
import tempfile
import matplotlib.pyplot as plt
import os

st.set_page_config(page_title="Trip Expense Manager", layout="wide")

DEFAULT_TRIP = "Trip 1"

if 'trips' not in st.session_state:
    st.session_state.trips = {DEFAULT_TRIP: {
        'members': [],
        'advances': defaultdict(lambda: defaultdict(float)),
        'expenses': [],
        'transactions': [],
        'settlements': [],
        'advance_usage_map': defaultdict(lambda: defaultdict(float)),
        'summary': defaultdict(lambda: {
            'advance_given': 0.0,
            'advance_received': 0.0,
            'advance_used_by_others': 0.0,
            'advance_used_from_others': 0.0,
            'advance_balance': 0.0,
            'own_paid': 0.0,
            'share': 0.0,
            'owes_to': defaultdict(float),
            'gets_from': defaultdict(float)
        })
    }}

trip_names = list(st.session_state.trips.keys())
current_trip = st.sidebar.selectbox("Select Trip", trip_names)
trip = st.session_state.trips[current_trip]

# -- Add Members
# Sidebar section to add new members to the trip
st.sidebar.header("Add Members")  # Add a header for the member addition section in the sidebar

# Input field to enter the name of a new member
new_member = st.sidebar.text_input("New Member")

# Button to add the new member to the trip
if st.sidebar.button("Add Member") and new_member and new_member not in trip['members']:
    # Add the new member to the list of trip members
    trip['members'].append(new_member)
    # Display a success message confirming the addition
    st.success(f"Added {new_member}")

# --- Record Advance ---
st.header("1. Record Advance")

# Create three columns for input fields
col1, col2, col3 = st.columns(3)

# Dropdown to select the member giving the advance
with col1:
    adv_from = st.selectbox("Advance From", trip['members'])

# Dropdown to select the treasurer receiving the advance
with col2:
    adv_to = st.selectbox("Advance To (Treasurer)", trip['members'])

# Input field to specify the advance amount
with col3:
    adv_amt = st.number_input("Advance Amount", min_value=0.0, step=100.0)

# Button to record the advance transaction
if st.button("Add Advance"):
    # Ensure the advance is not being paid to oneself
    if adv_from != adv_to:
        # Update the advance data for the trip
        trip['advances'][adv_to][adv_from] += adv_amt
        trip['summary'][adv_from]['advance_given'] += adv_amt
        trip['summary'][adv_from]['advance_balance'] += adv_amt
        trip['summary'][adv_to]['advance_received'] += adv_amt

        # Record the transaction in the trip's history
        trip['transactions'].append(f"Advance: {adv_from} gave Rs. {adv_amt} to {adv_to}")

        # Display a success message
        st.success("Advance recorded")
    else:
        # Display a warning if the advance is being paid to oneself
        st.warning("Cannot pay advance to self")

# --- Record Expense ---
st.header("2. Record Expense")
with st.form("expense_form"):
    payer = st.selectbox("Paid By", trip['members'])
    amount = st.number_input("Expense Amount", min_value=0.0)
    participants = st.multiselect("Shared Between", trip['members'], default=trip['members'])
    reason = st.text_input("Reason / Description")
    submit = st.form_submit_button("Add Expense")

    if submit and amount > 0 and participants:
        per_head = round(amount / len(participants), 2)
        original_amount = amount

        if payer in trip['advances']:
            used_advance_total = 0
            advance_remaining = {k: v for k, v in trip['advances'][payer].items()}
            contributors = sorted(advance_remaining.items(), key=lambda x: -x[1])
            share_source_map = defaultdict(list)

            for person in participants:
                share_remaining = per_head

                # First, use participant's own advance if available
                if person in advance_remaining and advance_remaining[person] > 0:
                    use = min(share_remaining, advance_remaining[person])
                    advance_remaining[person] -= use
                    share_source_map[person].append((person, use))
                    share_remaining -= use
                    used_advance_total += use

                # Then use other contributors' advance
                for contributor, _ in contributors:
                    if contributor == person:
                        continue
                    if share_remaining <= 0 or advance_remaining[contributor] <= 0:
                        continue
                    use = min(share_remaining, advance_remaining[contributor])
                    advance_remaining[contributor] -= use
                    share_source_map[person].append((contributor, use))
                    share_remaining -= use
                    used_advance_total += use

                # Remainder paid by treasurer
                if share_remaining > 0:
                    share_source_map[person].append((payer, share_remaining))

            # Attribution
            for person, sources in share_source_map.items():
                for contributor, amt in sources:
                    if amt <= 0 or person == contributor:
                        continue
                    trip['summary'][person]['owes_to'][contributor] += amt
                    trip['summary'][contributor]['gets_from'][person] += amt

                    if contributor in trip['advances'][payer]:
                        trip['summary'][person]['advance_used_from_others'] += amt
                        trip['summary'][contributor]['advance_used_by_others'] += amt
                        trip['summary'][contributor]['advance_balance'] -= amt
                    elif contributor == payer:
                        trip['summary'][contributor]['own_paid'] += amt

            for contributor in trip['advances'][payer]:
                trip['advances'][payer][contributor] = advance_remaining.get(contributor, 0.0)

        else:
            own_payment = original_amount
            trip['summary'][payer]['own_paid'] += round(own_payment, 2)

            if own_payment > 0:
                equal_own_share = round(own_payment / len(participants), 2)
                for person in participants:
                    if person != payer:
                        if payer in trip['advances'] and person in trip['advances'][payer]:
                            trip['summary'][person]['advance_used_from_others'] += equal_own_share
                            trip['summary'][payer]['advance_used_by_others'] += equal_own_share
                            trip['summary'][person]['advance_balance'] -= equal_own_share
                        else:
                            trip['summary'][person]['owes_to'][payer] += equal_own_share
                            trip['summary'][payer]['gets_from'][person] += equal_own_share

        for person in participants:
            trip['summary'][person]['share'] += per_head

        trip['expenses'].append({
            'payer': payer,
            'amount': amount,
            'shared_by': participants,
            'reason': reason
        })
        trip['transactions'].append(f"Expense: {payer} paid Rs. {amount} for {', '.join(participants)} - {reason}")
        st.success("Expense recorded")

# --- Settle Dues ---
# Section for settling dues between members
st.header("3. Settle Dues")

# Create three columns for input fields
col1, col2, col3 = st.columns(3)

# Dropdown to select the member who is paying
with col1:
    settle_from = st.selectbox("Who is paying?", trip['members'])

# Dropdown to select the member who is receiving the payment
with col2:
    settle_to = st.selectbox("Who is receiving?", [m for m in trip['members'] if m != settle_from])

# Text input for an optional note about the settlement
with col3:
    note = st.text_input("Optional Note")

# Get the amount owed by the payer to the receiver
owed_amt = trip['summary'][settle_from]['owes_to'].get(settle_to, 0.0)

# Check if there is any amount owed
if owed_amt > 0:
    # Input field to specify the settlement amount, with a default value of the owed amount
    settle_amt = st.number_input("Settlement Amount", min_value=0.0, max_value=owed_amt, step=50.0, value=owed_amt)
    
    # Button to mark the settlement as completed
    if st.button("Mark as Settled"):
        # Calculate the amount to be paid (minimum of entered amount and owed amount)
        pay_amt = min(settle_amt, owed_amt)
        
        # Update the summary data to reflect the settlement
        trip['summary'][settle_from]['owes_to'][settle_to] -= pay_amt
        trip['summary'][settle_to]['gets_from'][settle_from] -= pay_amt
        
        # Remove entries if the amounts are fully settled
        if trip['summary'][settle_from]['owes_to'][settle_to] <= 0:
            del trip['summary'][settle_from]['owes_to'][settle_to]
        if trip['summary'][settle_to]['gets_from'][settle_from] <= 0:
            del trip['summary'][settle_to]['gets_from'][settle_from]
        
        # Record the settlement in the settlements list
        trip['settlements'].append({
            "from": settle_from,
            "to": settle_to,
            "amount": pay_amt,
            "note": note,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Add the settlement to the transaction history
        trip['transactions'].append(f"Settlement: {settle_from} paid Rs. {pay_amt} to {settle_to} ({note})")
        
        # Display success message and remaining balance
        st.success(f"Rs. {pay_amt} settled between {settle_from} → {settle_to}")
        st.info(f"Remaining: Rs. {round(owed_amt - pay_amt, 2)}")
else:
    # Display a warning if there are no pending dues between the selected members
    st.warning(f"No pending dues from {settle_from} to {settle_to}.")

# --- Summary Table ---
st.header("4. Member Summary Table")
sum_rows = []
for name in trip['members']:
    s = trip['summary'][name]
    gets = sum(v for k, v in s['gets_from'].items() if k != name)
    owes = sum(v for k, v in s['owes_to'].items() if k != name)
    status = "Settled" if owes == 0 and gets == 0 else "Pending"
    sum_rows.append({
        "Name": name,
        "Advance Given": s['advance_given'],
        "Advance Received": s['advance_received'],
        "Advance Used By Others": s['advance_used_by_others'],
        "Advance Used From Others": s['advance_used_from_others'],
        "Advance Balance": s['advance_balance'],
        "Own Paid": s['own_paid'],
        "Share": s['share'],
        "Gets Back": gets,
        "Owes": owes,
        "Net": round(gets - owes, 2),
        "Status": status
    })
st.dataframe(pd.DataFrame(sum_rows), use_container_width=True)

# --- Individual Member Details ---
st.header("5. Individual Member Details")
selected_member = st.selectbox("Select Member to View Details", trip['members'])
if selected_member:
    s = trip['summary'][selected_member]
    st.subheader(f"Details for {selected_member}")
    st.markdown(f"**Advance Given:** Rs. {s['advance_given']}")
    st.markdown(f"**Advance Received:** Rs. {s['advance_received']}")
    st.markdown(f"**Advance Used By Others:** Rs. {s['advance_used_by_others']}")
    st.markdown(f"**Advance Used From Others:** Rs. {s['advance_used_from_others']}")
    st.markdown(f"**Advance Balance:** Rs. {s['advance_balance']}")
    st.markdown(f"**Own Paid:** Rs. {s['own_paid']}")
    st.markdown(f"**Share in Expenses:** Rs. {s['share']}")

    if s['owes_to']:
        st.markdown("### Owes To")
        for person, amt in s['owes_to'].items():
            st.markdown(f"- Rs. {amt} to {person}")
    if s['gets_from']:
        st.markdown("### Gets From")
        for person, amt in s['gets_from'].items():
            st.markdown(f"- Rs. {amt} from {person}")

# --- JSON Export ---
st.header("6. Export Data to JSON")
json_data = {
    "members": trip['members'],
    "advances": {k: dict(v) for k, v in trip['advances'].items()},
    "expenses": trip['expenses'],
    "transactions": trip['transactions'],
    "settlements": trip['settlements'],
    "summary": {k: {
        **v,
        "owes_to": {k2: v2 for k2, v2 in v['owes_to'].items() if k2 != k},
        "gets_from": {k2: v2 for k2, v2 in v['gets_from'].items() if k2 != k}
    } for k, v in trip['summary'].items()}
}
st.download_button("Download JSON", data=json.dumps(json_data, indent=2), file_name="trip_data_export.json", mime="application/json")

# --- PDF Export ---
st.header("7. Export PDF Summary")
class PDF(FPDF):
    def header(self):
        """
        Adds a header to each page of the PDF.
        The header includes the trip name and is centered at the top of the page.
        """
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, f"Trip Summary - {current_trip}", ln=1, align='C')
        self.ln(5)

    def chapter_title(self, title):
        """
        Adds a chapter title to the PDF.
        Args:
            title (str): The title of the chapter.
        """
        self.set_font('Arial', 'B', 12)
        self.cell(0, 8, title, ln=1)
        self.ln(2)

    def chapter_body(self, text):
        """
        Adds the body text for a chapter.
        Args:
            text (str): The content of the chapter.
        """
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, text)
        self.ln()

    def add_member_summary(self, name, s):
        """
        Adds a summary for an individual member to the PDF.
        Args:
            name (str): The name of the member.
            s (dict): The summary data for the member.
        """
        self.set_font('Arial', 'B', 10)
        self.cell(0, 6, name, ln=1)
        self.set_font('Arial', '', 9)
        # Add key financial details for the member
        lines = [
            f"Advance Given: Rs. {s['advance_given']}",
            f"Advance Received: Rs. {s['advance_received']}",
            f"Advance Used By Others: Rs. {s['advance_used_by_others']}",
            f"Advance Used From Others: Rs. {s['advance_used_from_others']}",
            f"Advance Balance: Rs. {s['advance_balance']}",
            f"Own Paid: Rs. {s['own_paid']}",
            f"Share: Rs. {s['share']}"
        ]
        for line in lines:
            self.cell(0, 5, line, ln=1)
        # Add details of amounts owed to others
        if s['owes_to']:
            self.set_text_color(255, 0, 0)  # Red for "owes to"
            self.cell(0, 5, "Owes to:", ln=1)
            for k, v in s['owes_to'].items():
                self.cell(0, 5, f"- Rs. {v} to {k}", ln=1)
        # Add details of amounts received from others
        if s['gets_from']:
            self.set_text_color(0, 128, 0)  # Green for "gets from"
            self.cell(0, 5, "Gets from:", ln=1)
            for k, v in s['gets_from'].items():
                self.cell(0, 5, f"- Rs. {v} from {k}", ln=1)
        self.set_text_color(0, 0, 0)  # Reset text color to black
        self.ln(4)

    def add_summary_table(self, summary_rows):
        """
        Adds a summary table to the PDF document.

        This method generates a table with headers and rows based on the provided
        summary data. The table includes details such as name, advances, balances,
        payments, and net amounts.

        Args:
            summary_rows (list of dict): A list of dictionaries where each dictionary
                represents a row in the summary table. Each dictionary should have
                the following keys:
                    - "Name" (str): The name of the individual.
                    - "Advance Given" (float): The amount of advance given.
                    - "Advance Received" (float): The amount of advance received.
                    - "Advance Used By Others" (float): The amount of advance used by others.
                    - "Advance Balance" (float): The remaining balance of the advance.
                    - "Own Paid" (float): The amount paid by the individual.
                    - "Share" (float): The individual's share of the total expenses.
                    - "Gets Back" (float): The amount the individual gets back.
                    - "Owes" (float): The amount the individual owes.
                    - "Net" (float): The net amount (gets back - owes).

        Notes:
            - The table is styled with specific fonts and colors.
            - Column widths are predefined to ensure proper alignment.
            - Each row of data is added to the table sequentially.
            - A blank line is added after the table for spacing.

        Example:
            summary_rows = [
                {
                    "Name": "Alice",
                    "Advance Given": 100.0,
                    "Advance Received": 50.0,
                    "Advance Used By Others": 30.0,
                    "Advance Balance": 20.0,
                    "Own Paid": 200.0,
                    "Share": 150.0,
                    "Gets Back": 50.0,
                    "Owes": 0.0,
                    "Net": 50.0
                },
                ...
            ]
            pdf.add_summary_table(summary_rows)
        """
        self.set_text_color(0, 0, 0)  # Black text color
        self.set_font('Arial', 'B', 11)
        self.cell(0, 8, "Trip Summary Table", ln=1)
        self.set_font('Arial', '', 8)
        # Define table headers and column widths
        headers = ["Name", "Adv Given", "Adv Recvd", "Adv Used", "Balance", "Own Paid", "Share", "Gets", "Owes", "Net"]
        col_widths = [25, 18, 18, 20, 18, 18, 18, 18, 18, 18]
        # Add table headers
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 6, header, border=1)
        self.ln()
        # Add table rows
        for row in summary_rows:
            self.cell(col_widths[0], 6, row["Name"], border=1)
            self.cell(col_widths[1], 6, str(row["Advance Given"]), border=1)
            self.cell(col_widths[2], 6, str(row["Advance Received"]), border=1)
            self.cell(col_widths[3], 6, str(row["Advance Used By Others"]), border=1)
            self.cell(col_widths[4], 6, str(row["Advance Balance"]), border=1)
            self.cell(col_widths[5], 6, str(row["Own Paid"]), border=1)
            self.cell(col_widths[6], 6, str(row["Share"]), border=1)
            self.cell(col_widths[7], 6, str(row["Gets Back"]), border=1)
            self.cell(col_widths[8], 6, str(row["Owes"]), border=1)
            self.cell(col_widths[9], 6, str(row["Net"]), border=1)
            self.ln()
        self.ln()  # Add a blank line after the table

if st.button("Generate PDF Summary"):
    # Create a new PDF instance
    pdf = PDF()
    pdf.add_page()

    # Prepare summary rows for the table
    sum_rows = []
    for name in trip['members']:
        s = trip['summary'][name]
        gets = sum(v for k, v in s['gets_from'].items() if k != name)  # Total amount the member gets back
        owes = sum(v for k, v in s['owes_to'].items() if k != name)  # Total amount the member owes
        net = round(gets - owes, 2)  # Net balance (gets back - owes)
        sum_rows.append({
            "Name": name,
            "Advance Given": s['advance_given'],
            "Advance Received": s['advance_received'],
            "Advance Used By Others": s['advance_used_by_others'],
            "Advance Balance": s['advance_balance'],
            "Own Paid": s['own_paid'],
            "Share": s['share'],
            "Gets Back": gets,
            "Owes": owes,
            "Net": net
        })
    # Add the summary table to the PDF
    pdf.add_summary_table(sum_rows)

    # Add individual member details to the PDF
    for m in trip['members']:
        pdf.add_member_summary(m, trip['summary'][m])

    # Add a new page for activity history
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "Activity History", ln=1)
    pdf.set_font('Arial', '', 9)
    for entry in trip['transactions']:
        # Set text color based on the type of transaction
        if entry.startswith("Advance:"):
            pdf.set_text_color(0, 0, 255)  # Blue for Advance
        elif entry.startswith("Expense:"):
            pdf.set_text_color(0, 128, 0)  # Green for Expense
        elif entry.startswith("Settlement:"):
            pdf.set_text_color(255, 0, 0)  # Red for Settlement
        else:
            pdf.set_text_color(0, 0, 0)  # Default color
        pdf.cell(0, 6, entry, ln=1)
    pdf.set_text_color(0, 0, 0)  # Reset text color to black

    # Generate a pie chart for contributions by members
    fig, ax = plt.subplots()
    totals = [trip['summary'][m]['own_paid'] for m in trip['members']]  # Total contributions by each member
    ax.pie(totals, labels=trip['members'], autopct='%1.1f%%', startangle=90)
    plt.title("Contribution by Members")
    chart_path = os.path.join(tempfile.gettempdir(), "trip_pie_chart.png")
    plt.savefig(chart_path)  # Save the pie chart as an image
    plt.close()
    pdf.image(chart_path, x=10, w=180)  # Add the pie chart image to the PDF

    # Generate a bar chart for net balances
    net_values = [row["Net"] for row in sum_rows]  # Net balances for each member
    fig, ax = plt.subplots()
    bars = ax.bar(trip['members'], net_values)  # Create a bar chart
    plt.title("Net Balance per Member")
    plt.xticks(rotation=45)  # Rotate x-axis labels for better readability
    bar_chart_path = os.path.join(tempfile.gettempdir(), "bar_chart.png")
    plt.savefig(bar_chart_path, bbox_inches='tight')  # Save the bar chart as an image
    plt.close()
    pdf.image(bar_chart_path, x=10, w=180)  # Add the bar chart image to the PDF

    # Save the PDF to a temporary file and provide a download button
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        pdf.output(tmp_file.name)  # Save the PDF to the temporary file
        st.download_button("Download PDF", open(tmp_file.name, "rb"), file_name="trip_summary.pdf", mime="application/pdf")
