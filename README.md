
# Trip Expense Manager

## 🌟 Goal
To manage and track expenses among a group of people during a trip where:
- Some members may give advance money to a designated treasurer
- Expenses can be recorded by any member and shared among selected participants
- Fair debt attribution is maintained based on who paid, who participated, and who provided advance
- Final settlements are clearly displayed

## ⚙️ Logic
- **Advance Flow**: Members can send advance money to a treasurer. This money is treated as the contributor's credit.
- **Expense Flow**: When a treasurer spends, participants' shares are deducted from their own advance first (if provided). Remaining share is covered by other contributors' advance or treated as debt.
- **Non-treasurer Expense**: If a member spends from their pocket, each participant owes their split share to the payer directly.
- **Settlements**: Members can mark payments made to clear dues.

## 📈 Features
- ✅ Add members dynamically
- ✅ Record advances from any member to any treasurer
- ✅ Add detailed expenses with description and share-split
- ✅ Automatically adjusts dues using available advance
- ✅ Shows summary table per member (advance, share, dues, paid, net)
- ✅ Visual charts (pie & bar) for contributions and balances
- ✅ Detailed per-member report (what they owe, what they get)
- ✅ Full activity history
- ✅ Export all data to JSON and PDF
- ✅ Color-coded PDF export (Advance = blue, Expense = green, Settlement = red)

## 📖 How to Use

### 1. **Install Requirements**
```bash
pip install streamlit fpdf matplotlib pandas
```

### 2. **Run the App**
```bash
streamlit run trip_expense_app.py
```

### 3. **Use the Interface**
- Add all trip members
- Record any advance payments given to a treasurer
- Log expenses and choose who split the cost
- View member-wise summary, transactions, and settlement options
- Export to PDF or JSON anytime

## 🔄 Example
1. A & B give ₹3000 each to C (Treasurer)
2. C pays ₹10000, split among 8 people
3. System deducts everyone’s share from their own advance if they paid
4. Remaining is tracked as owed to advance contributors or payer
5. Summary shows exactly who owes what to whom

## 🎨 Visuals in PDF
- Pie Chart: Contribution by Members
- Bar Chart: Net Balance
- Activity Log: Advance / Expense / Settlement, all color-coded

## 📁 File Export
- `trip_data_export.json`: Complete data backup
- `trip_summary.pdf`: Styled summary with tables, charts, and logs

---
**Made with ❤️ for simplifying group expense tracking.**
