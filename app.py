import customtkinter as ctk
import pandas as pd
import os
import time
import json
import requests
from datetime import datetime

# --- CONFIGURATION ---
EXCEL_FILE = "finance_data.xlsx"
RATES_FILE = "rates_cache.json"
CURRENCY_API = "https://api.frankfurter.app/latest?from=USD"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DataManager:
    def __init__(self):
        self.check_files()

    def check_files(self):
        if not os.path.exists(EXCEL_FILE):
            # Create empty sheets if file doesn't exist
            with pd.ExcelWriter(EXCEL_FILE) as writer:
                pd.DataFrame(columns=["id", "date", "note", "account", "category", "amount", "t_type"]).to_excel(writer, sheet_name="Transactions", index=False)
                pd.DataFrame(columns=["name", "type", "currency", "initial_balance"]).to_excel(writer, sheet_name="Accounts", index=False)
                pd.DataFrame(columns=["category_name", "type"]).to_excel(writer, sheet_name="Categories", index=False)
    
    def get_data(self, sheet_name):
        return pd.read_excel(EXCEL_FILE, sheet_name=sheet_name)

    def add_category(self, name, cat_type):
        df=self.get_data("Categories")
        new_row={
            "category_name": name,
            "type": cat_type
        }
        df=pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        with pd.ExcelWriter(EXCEL_FILE, mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name="Categories", index=False)

    def add_transaction(self, date, note, account, category, amount, t_type):
        df = self.get_data("Transactions")
        new_row = {
            "id": len(df) + 1,
            "date": date,
            "note": note,
            "account": account,
            "category": category,
            "amount": float(amount),
            "type": t_type
        }
        # Concat is the modern pandas way to append
        new_df=pd.DataFrame([new_row])
        if df.empty:
            df=new_df
        else:
            df = pd.concat([df, new_df], ignore_index=True)
        
        with pd.ExcelWriter(EXCEL_FILE, mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name="Transactions", index=False)

    def get_summary(self):
        # Calculates totals using Pandas (replaces SQL Queries)
        trans = self.get_data("Transactions")
        if trans.empty:
            return 0, 0, 0
            
        income = trans[(trans['type'] == 'Income') & (trans['category']!='Initial Balance')]['amount'].sum()
        expense = trans[trans['type'] == 'Expense']['amount'].sum()
        total = income - expense
        return total, income, expense

class CurrencyManager:
    """Handles Internet logic. Updates only every 24 hours."""
    def get_rates(self):
        now = time.time()
        
        # 1. Try to load from cache
        if os.path.exists(RATES_FILE):
            with open(RATES_FILE, 'r') as f:
                data = json.load(f)
                # If cache is younger than 24 hours (86400 seconds), use it
                if now - data['timestamp'] < 86400:
                    print("Using Cached Rates")
                    return data['rates']

        # 2. Fetch from Internet if cache is old or missing
        try:
            print("Fetching New Rates from Internet...")
            response = requests.get(CURRENCY_API)
            rates = response.json()['rates']
            rates['USD'] = 1.0 # Base
            
            # Save to cache
            with open(RATES_FILE, 'w') as f:
                json.dump({'timestamp': now, 'rates': rates}, f)
            return rates
        except:
            print("Offline mode: Using default rates")
            return {'TRY': 40.0, 'USD': 1.0, 'EUR': 0.9}

class FinanceApp(ctk.CTk):
    """The Main GUI Window"""
    def __init__(self):
        super().__init__()
        self.db = DataManager()
        self.cm = CurrencyManager()
        self.rates = self.cm.get_rates()

        self.title("FinanceTrack Desktop")
        self.geometry("900x600")

        # --- LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="📊 FinanceTrack", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=20)

        self.btn_dash = ctk.CTkButton(self.sidebar, text="Dashboard", command=self.show_dashboard)
        self.btn_dash.grid(row=1, column=0, padx=20, pady=10)

        self.btn_add = ctk.CTkButton(self.sidebar, text="Add Transaction", command=self.show_add_frame)
        self.btn_add.grid(row=2, column=0, padx=20, pady=10)

        self.btn_add = ctk.CTkButton(self.sidebar, text="Add Category", command=self.show_add_category)
        self.btn_add.grid(row=3, column=0, padx=20, pady=10)

        self.btn_add = ctk.CTkButton(self.sidebar, text="Clear Data", command=self.clear_data)
        self.btn_add.grid(row=4, column=0, padx=20, pady=10)
        



        # 2. Main Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        #Fix the transactions dashboard
        
        self.show_dashboard()


    def clear_data(self):
        if os.path.exists(EXCEL_FILE):
            try:
                os.remove(EXCEL_FILE)
                print("Succesfull deletion")
            except PermissionError:
                print("File is Open")
                return
            self.db.check_files()
            self.show_dashboard()
        else:
            print("File not found. Creation...")
            self.db.check_files()
            print("Completed")
            self.show_dashboard()


    def clear_main(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def show_dashboard(self):
        self.clear_main()
        total, income, expense = self.db.get_summary()
        
        # Stats Cards
        stats_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        stats_frame.pack(fill="x", pady=10)

        self.create_stat_card(stats_frame, "Total Balance", f"{total:.2f}", "blue")
        self.create_stat_card(stats_frame, "Income", f"+{income:.2f}", "green")
        self.create_stat_card(stats_frame, "Expense", f"-{expense:.2f}", "red")
        
        # Recent List (Mini Table) Fix this 
        ctk.CTkLabel(self.main_frame, text="Recent Transactions", font=("Arial", 16, "bold")).pack(anchor="w", pady=(20, 10))
        
        df = self.db.get_data("Transactions").tail(10) # Get last 10
        text_area = ctk.CTkTextbox(self.main_frame, width=600, height=300)
        text_area.pack(fill="both", expand=True)
        
        # Simple display of dataframe as text
        if not df.empty:
            text_area.insert("0.0", df[['date', 'account', 'category', 'amount']].to_string(index=False))
        else:
            text_area.insert("0.0", "No transactions yet.")
        text_area.configure(state="disabled")

    def create_stat_card(self, parent, title, value, color):
        card = ctk.CTkFrame(parent, width=200, height=100)
        card.pack(side="left", expand=True, fill="both", padx=5)
        ctk.CTkLabel(card, text=title, text_color="gray").pack(pady=(10,0))
        lbl = ctk.CTkLabel(card, text=value, font=("Arial", 24, "bold"))
        lbl.pack(pady=5)
        if color == "green": lbl.configure(text_color="#10B981")
        if color == "red": lbl.configure(text_color="#EF4444")

    def show_add_frame(self):
        self.clear_main()
        ctk.CTkLabel(self.main_frame, text="Add Transaction", font=("Arial", 20, "bold")).pack(pady=20)

        self.entry_amount = ctk.CTkEntry(self.main_frame, placeholder_text="Amount")
        self.entry_amount.pack(pady=10)

        self.entry_note = ctk.CTkEntry(self.main_frame, placeholder_text="Note")
        self.entry_note.pack(pady=10)

        df=self.db.get_data("Categories")
        cats=list(df["category_name"])
        self.combo_type = ctk.CTkComboBox(self.main_frame, values=cats)
        self.combo_type.pack(pady=10)

        ctk.CTkButton(self.main_frame, text="Save", command=self.save_transaction).pack(pady=20)

    def show_add_category(self):
        self.clear_main()
        ctk.CTkLabel(self.main_frame, text="Add Category", font=("Arial", 20, "bold")).pack(pady=20)

        self.entry_name = ctk.CTkEntry(self.main_frame, placeholder_text="name")
        self.entry_name.pack(pady=10)

        self.cat_type = ctk.CTkComboBox(self.main_frame, values=["Expense", "Income"])
        self.cat_type.pack(pady=10)

        ctk.CTkButton(self.main_frame, text="Save", command=self.save_category).pack(pady=20)

    def save_transaction(self):
        amt = self.entry_amount.get()
        note = self.entry_note.get()
        cat = self.combo_type.get()
        df= self.db.get_data("Categories")

        matching_rows = df.loc[df["category_name"] == cat, "type"]
        if matching_rows.empty:
            print("Error: Category not found")
            return
        typ=matching_rows.iloc[0]
        
        if amt:
            self.db.add_transaction(
                date=datetime.now().strftime("%Y-%m-%d"),
                note=note,
                account="Cash", # You would make this a dropdown in full version
                category=cat,
                amount=amt,
                t_type=typ
            )
            self.show_dashboard()
    
    def save_category(self):
        name=self.entry_name.get()
        cat_type=self.cat_type.get()
        if name and cat_type:
            self.db.add_category(
                name,
                cat_type
            )
        self.show_dashboard()



if __name__ == "__main__":
    app = FinanceApp()
    app.mainloop()