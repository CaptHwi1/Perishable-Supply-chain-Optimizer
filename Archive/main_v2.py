import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import pulp as pl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os


class PerishableSupplyChain:
    def __init__(self, products, distributors, transport_rate=0.01, sim_days_override=None):
        """
        Args:
            products: dict {product_name: {'shelf_life': int, 'production_plan': dict}}
            distributors: list of dict with name, policy_days, proportion, distance_km, purchase_days, preferred_products
            transport_rate: $/km/unit
            sim_days_override: total simulation days
        """
        self.products = products
        self.distributors = distributors
        self.transport_rate = transport_rate
        self.sim_days_override = sim_days_override
        self.all_results = {}
        self.total_transport_cost = 0.0
        self.total_waste_cost = 0.0

    def run_simulation(self):
        """Run simulation for all products"""
        self.all_results = {}
        self.total_transport_cost = 0.0
        self.total_waste_cost = 0.0

        for prod_name, prod_data in self.products.items():
            shelf_life = prod_data['shelf_life']
            production_plan = prod_data['production_plan']
            total_days = self.sim_days_override

            batches = {}
            purchases = []
            inventory_log = []
            waste = {}

            # Simulate day-by-day
            for current_day in range(1, total_days + 1):
                # Add new batch if produced today
                if current_day in production_plan and production_plan[current_day] > 0:
                    qty = production_plan[current_day]
                    batches[current_day] = {
                        'initial': qty,
                        'current': qty,
                        'expiry': current_day + shelf_life - 1
                    }

                # Log inventory at start
                log_entry = {'Day': current_day, 'Phase': 'Start'}
                for b_day in sorted(batches.keys()):
                    log_entry[f'Q{b_day}'] = int(batches[b_day]['current'])
                inventory_log.append(log_entry)

                # Remove expired batches at end of their expiry day
                expired_days = [p_day for p_day, b in list(batches.items()) if b['expiry'] == current_day]
                for p_day in expired_days:
                    final_qty = batches[p_day]['current']
                    waste[p_day] = final_qty
                    del batches[p_day]

                # Process distributors in priority order (by policy_days)
                sorted_distributors = sorted(self.distributors, key=lambda x: x['policy_days'])
                
                for dist in sorted_distributors:
                    # Skip if distributor doesn't carry this product
                    if prod_name not in dist['preferred_products']:
                        continue
                        
                    dist_name = dist['name']
                    policy = dist['policy_days']
                    proportion = round(dist['proportion'], 2)
                    distance = dist['distance_km']

                    # Skip if not a purchase day or it's Sunday
                    if (current_day > len(dist['purchase_days']) or 
                        not dist['purchase_days'][current_day - 1] or 
                        current_day % 7 == 0):
                        continue

                    # Valid batches: age < policy AND still in inventory
                    valid_batches = {
                        p_day: b for p_day, b in batches.items()
                        if (current_day - p_day) < policy and b['current'] > 0
                    }

                    if not valid_batches:
                        continue

                    # Total available from valid batches
                    total_available = sum(b['current'] for b in valid_batches.values())
                    total_purchase = int(round(proportion * total_available))

                    # Distribute purchase across valid batches
                    remaining_purchase = total_purchase
                    sorted_batches = sorted(valid_batches.items(), key=lambda x: x[0])

                    for p_day, batch in sorted_batches[:-1]:
                        share = int(round((batch['current'] / total_available) * total_purchase))
                        share = min(share, batch['current'], remaining_purchase)
                        batch['current'] -= share
                        remaining_purchase -= share

                        if share > 0:
                            transport_cost = share * distance * self.transport_rate
                            self.total_transport_cost += transport_cost
                            
                            purchases.append({
                                'Product': prod_name,
                                'Day': current_day,
                                'Distributor': dist_name,
                                'Batch_Day': p_day,
                                'Quantity': share,
                                'Shelf_Age': current_day - p_day,
                                'Policy': policy,
                                'Proportion': proportion,
                                'Transport_Cost': transport_cost
                            })

                    # Give remainder to last batch
                    if sorted_batches:
                        p_day, batch = sorted_batches[-1]
                        final_share = min(remaining_purchase, batch['current'])
                        batch['current'] -= final_share

                        if final_share > 0:
                            transport_cost = final_share * distance * self.transport_rate
                            self.total_transport_cost += transport_cost
                            
                            purchases.append({
                                'Product': prod_name,
                                'Day': current_day,
                                'Distributor': dist_name,
                                'Batch_Day': p_day,
                                'Quantity': final_share,
                                'Shelf_Age': current_day - p_day,
                                'Policy': policy,
                                'Proportion': proportion,
                                'Transport_Cost': transport_cost
                            })

                    # Remove empty batches
                    for p_day in list(valid_batches.keys()):
                        if batches[p_day]['current'] <= 0:
                            del batches[p_day]

                # Log after transactions
                log_entry = {'Day': current_day, 'Phase': 'End'}
                for b_day in sorted(batches.keys()):
                    log_entry[f'Q{b_day}'] = int(batches[b_day]['current'])
                inventory_log.append(log_entry)

            # Compile results
            purchases_df = pd.DataFrame(purchases)
            
            # Waste data
            waste_data = []
            for day in range(1, total_days + 1):
                initial = production_plan.get(day, 0)
                if initial > 0:
                    expired = waste.get(day, 0)
                    waste_pct = (expired / initial) * 100 if initial > 0 else 0
                    waste_data.append({
                        'Product': prod_name,
                        'Batch_Day': day,
                        'Initial': initial,
                        'Waste': expired,
                        'Waste_Pct': round(waste_pct, 2),
                        'Waste_Pct_Display': f"{round(waste_pct, 2)}%"
                    })
                else:
                    waste_data.append({
                        'Product': prod_name,
                        'Batch_Day': day,
                        'Initial': 0,
                        'Waste': 0,
                        'Waste_Pct': 0.0,
                        'Waste_Pct_Display': "0.00%"
                    })
            waste_df = pd.DataFrame(waste_data)

            # Batch pivot table
            if not purchases_df.empty:
                pivot = purchases_df.pivot_table(
                    index='Distributor',
                    columns='Batch_Day',
                    values='Quantity',
                    aggfunc='sum',
                    fill_value=0
                ).round(0).astype(int)
                # Ensure all days are present
                for day in range(1, total_days + 1):
                    if day not in pivot.columns:
                        pivot[day] = 0
                pivot = pivot[sorted(pivot.columns)]
            else:
                pivot = pd.DataFrame()

            self.all_results[prod_name] = {
                'purchases': purchases_df,
                'waste': waste_df,
                'batch_pivot': pivot,
                'inventory_log': pd.DataFrame(inventory_log)
            }

        return self.all_results

    def optimize_production(self, sim_days, shelf_life):
        """LP to recommend optimal production plan minimizing waste + transport"""
        days = list(range(1, sim_days + 1))
        x = pl.LpVariable.dicts("Produce", days, lowBound=0, cat='Integer')

        prob = pl.LpProblem("Minimize_Total_Cost", pl.LpMinimize)

        # Constants
        transport_rate = 0.01  # $/km/unit
        waste_cost_per_unit = 1.0  # Assumed cost

        # Objective: Minimize transport + estimated waste
        total_cost = 0
        for day in days:
            # Estimate waste cost (10% of production as proxy)
            total_cost += waste_cost_per_unit * x[day] * 0.1

            # Transport cost for units bought from batch produced on `day`
            for dist in self.distributors:
                # Only if within policy window and not Sunday
                for d in range(day, min(day + dist['policy_days'], sim_days + 1)):
                    if d % 7 != 0:  # Not Sunday
                        total_cost += x[day] * dist['proportion'] * transport_rate

        prob += total_cost

        # Constraint: No production on Sundays
        for day in days:
            if day % 7 == 0:
                prob += x[day] == 0

        # Solve
        prob.solve(pl.PULP_CBC_CMD(msg=False))

        recommendation = {day: int(x[day].varValue or 0) for day in days}
        return recommendation


class SupplyChainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Perishable Supply Chain Enterprise Optimizer")
        self.root.geometry("1400x900")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Theme variables
        self.is_dark_mode = True
        
        # Configuration
        self.products = {}
        self.distributors = []
        self.transport_rate = tk.DoubleVar(value=0.01)
        self.sim_days = tk.IntVar(value=28)
        self.all_results = {}
        self.optimized_production = {}
        
        # StringVars for entry widgets
        self.prod_name_var = tk.StringVar()
        self.prod_shelf_life_var = tk.StringVar()
        self.dist_name_var = tk.StringVar()
        self.dist_policy_var = tk.StringVar(value="1")
        self.dist_prop_var = tk.StringVar(value="0.15")
        self.dist_dist_var = tk.StringVar(value="10")
        self.prod_var = tk.StringVar()
        self.prod_day_var = tk.StringVar()
        self.prod_qty_var = tk.StringVar()
        
        # Variables for theme colors
        self.colors = self._get_colors()
        
        self.create_widgets()

    def _get_colors(self):
        """Return color scheme based on theme"""
        if self.is_dark_mode:
            return {
                'bg': '#1e1e1e',
                'fg': '#ffffff',
                'header_bg': '#0066cc',
                'frame_bg': '#2d2d2d',
                'button_bg': '#0056b3',
                'button_fg': '#ffffff',
                'entry_bg': '#3c3c3c',
                'entry_fg': '#ffffff',
                'tree_bg': '#2d2d2d',
                'tree_field': '#3c3c3c',
                'tree_text': '#ffffff'
            }
        else:
            return {
                'bg': '#f0f4f8',
                'fg': '#000000',
                'header_bg': '#007acc',
                'frame_bg': '#ffffff',
                'button_bg': '#007bff',
                'button_fg': '#ffffff',
                'entry_bg': '#ffffff',
                'entry_fg': '#000000',
                'tree_bg': '#ffffff',
                'tree_field': '#ffffff',
                'tree_text': '#000000'
            }

    def create_widgets(self):
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Update colors based on theme
        self.colors = self._get_colors()
        
        style.configure("TFrame", background=self.colors['frame_bg'])
        style.configure("TLabel", background=self.colors['frame_bg'], foreground=self.colors['fg'], font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=6)
        style.map("TButton",
                  foreground=[('pressed', 'white'), ('active', 'white')],
                  background=[('pressed', '#004080'), ('active', self.colors['button_bg'])])
        style.configure("Treeview", 
                       background=self.colors['tree_bg'],
                       fieldbackground=self.colors['tree_field'],
                       foreground=self.colors['tree_text'],
                       font=("Segoe UI", 9), 
                       rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        # Header
        header_frame = tk.Frame(self.root, bg=self.colors['header_bg'], padx=20, pady=15)
        header_frame.pack(fill="x")
        
        title_label = tk.Label(header_frame, text="Perishable Supply Chain Enterprise Optimizer", 
                              font=("Segoe UI", 18, "bold"), fg="white", bg=self.colors['header_bg'])
        title_label.pack(side="left")
        
        subtitle_label = tk.Label(header_frame, text="Optimize Production & Minimize Waste", 
                                  font=("Segoe UI", 10), fg="white", bg=self.colors['header_bg'])
        subtitle_label.pack(side="left", padx=10)
        
        # Theme toggle
        self.theme_btn = tk.Button(header_frame, text="", command=self.toggle_theme, 
                                  bg=self.colors['header_bg'], fg="white", bd=0, font=("Segoe UI", 9))
        self.theme_btn.pack(side="right")
        self.update_theme_button_text()  # Set initial button text

        # Main notebook
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True)

        # === CONFIGURATION TAB ===
        setup_notebook = ttk.Notebook(notebook)
        notebook.add(setup_notebook, text="Configuration")

        # Page 1: Products
        products_frame = ttk.Frame(setup_notebook)
        setup_notebook.add(products_frame, text="Products")
        
        # Control panel
        ctrl_frame = ttk.Frame(products_frame)
        ctrl_frame.pack(fill="x", pady=10, padx=10)
        
        ttk.Label(ctrl_frame, text="Simulation Days:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(ctrl_frame, textvariable=self.sim_days, width=8).pack(side=tk.LEFT, padx=5)

        ttk.Label(ctrl_frame, text="Transport Rate ($/km/unit):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(ctrl_frame, textvariable=self.transport_rate, width=8).pack(side=tk.LEFT, padx=5)

        # Products Section
        ttk.Label(products_frame, text="Products", font=("", 11, "bold")).pack(anchor="w", padx=10, pady=(20, 5))
        
        prod_frame = ttk.Frame(products_frame)
        prod_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(prod_frame, text="Name:").grid(row=0, column=0, sticky="e", padx=5)
        self.prod_name_entry = ttk.Entry(prod_frame, textvariable=self.prod_name_var, width=10)
        self.prod_name_entry.grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(prod_frame, text="Shelf Life:").grid(row=0, column=2, sticky="e", padx=5)
        self.prod_shelf_life_entry = ttk.Entry(prod_frame, textvariable=self.prod_shelf_life_var, width=6)
        self.prod_shelf_life_entry.grid(row=0, column=3, sticky="w", padx=5)
        
        ttk.Button(prod_frame, text="Add Product", command=self.add_product).grid(row=0, column=4, padx=10)
        
        # Product listbox
        self.prod_listbox = tk.Listbox(products_frame, height=6)
        self.prod_listbox.pack(fill="x", padx=10, pady=2)
        
        ttk.Button(products_frame, text="Remove Selected Product", 
                  command=self.remove_product).pack(padx=10, pady=2)

        # Page 2: Distributors
        dist_frame = ttk.Frame(setup_notebook)
        setup_notebook.add(dist_frame, text="Distributors")

        # Distributors Section
        ttk.Label(dist_frame, text="Distributors", font=("", 11, "bold")).pack(anchor="w", padx=10, pady=(20, 5))
        
        dist_setup_frame = ttk.Frame(dist_frame)
        dist_setup_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(dist_setup_frame, text="Name:").grid(row=0, column=0, sticky="e", padx=5)
        self.dist_name_entry = ttk.Entry(dist_setup_frame, textvariable=self.dist_name_var, width=10)
        self.dist_name_entry.grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(dist_setup_frame, text="Policy:").grid(row=0, column=2, sticky="e", padx=5)
        self.dist_policy_spin = ttk.Spinbox(dist_setup_frame, from_=1, to=30, textvariable=self.dist_policy_var, width=5)
        self.dist_policy_spin.grid(row=0, column=3, sticky="w", padx=5)
        
        ttk.Label(dist_setup_frame, text="Prop:").grid(row=0, column=4, sticky="e", padx=5)
        self.dist_prop_spin = ttk.Spinbox(dist_setup_frame, from_=0.01, to=1.0, increment=0.01, textvariable=self.dist_prop_var, width=6)
        self.dist_prop_spin.grid(row=0, column=5, sticky="w", padx=5)
        
        ttk.Label(dist_setup_frame, text="Dist(km):").grid(row=0, column=6, sticky="e", padx=5)
        self.dist_dist_entry = ttk.Entry(dist_setup_frame, textvariable=self.dist_dist_var, width=6)
        self.dist_dist_entry.grid(row=0, column=7, sticky="w", padx=5)
        
        ttk.Button(dist_setup_frame, text="Add Distributor", command=self.add_distributor).grid(row=0, column=8, padx=10)
        
        # Product selection for distributor
        self.prod_selection_frame = ttk.Frame(dist_frame)
        self.prod_selection_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(self.prod_selection_frame, text="Select products for distributor:").pack(anchor="w")
        
        self.prod_checkboxes = []
        self.prod_vars = []
        
        # Simulation days selection
        self.days_selection_frame = ttk.Frame(dist_frame)
        self.days_selection_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(self.days_selection_frame, text="Days distributor buys:").pack(anchor="w")
        
        self.day_vars = []
        days_frame = ttk.Frame(self.days_selection_frame)
        days_frame.pack(fill="x", padx=10)
        
        for i in range(7):
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            var = tk.BooleanVar(value=True if i < 6 else False)  # Default: buys Mon-Sat, not Sun
            self.day_vars.append(var)
            cb = ttk.Checkbutton(days_frame, text=day_names[i], variable=var)
            cb.pack(side=tk.LEFT, padx=5)

        # Distributor list
        self.dist_listbox = tk.Listbox(dist_frame, height=6)
        self.dist_listbox.pack(fill="x", padx=10, pady=2)
        
        ttk.Button(dist_frame, text="Remove Selected Distributor", 
                  command=self.remove_distributor).pack(padx=10, pady=2)

        # Page 3: Production Plan
        prod_plan_frame = ttk.Frame(setup_notebook)
        setup_notebook.add(prod_plan_frame, text="Production Plan")

        # Production Plan Section
        ttk.Label(prod_plan_frame, text="Production Plan", font=("", 11, "bold")).pack(anchor="w", padx=10, pady=(20, 5))
        
        input_frame = ttk.Frame(prod_plan_frame)
        input_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(input_frame, text="Product:").grid(row=0, column=0, sticky="e", padx=5)
        self.prod_combo = ttk.Combobox(input_frame, textvariable=self.prod_var, state="readonly", width=12)
        self.prod_combo.grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(input_frame, text="Day:").grid(row=0, column=2, sticky="e", padx=5)
        self.prod_day_entry = ttk.Entry(input_frame, textvariable=self.prod_day_var, width=6)
        self.prod_day_entry.grid(row=0, column=3, sticky="w", padx=5)
        
        ttk.Label(input_frame, text="Qty:").grid(row=0, column=4, sticky="e", padx=5)
        self.prod_qty_entry = ttk.Entry(input_frame, textvariable=self.prod_qty_var, width=8)
        self.prod_qty_entry.grid(row=0, column=5, sticky="w", padx=5)
        
        ttk.Button(input_frame, text="Add", command=self.add_production).grid(row=0, column=6, padx=5)
        ttk.Button(input_frame, text="Remove", command=self.remove_production).grid(row=0, column=7, padx=5)
        
        # Production tree
        self.prod_tree = ttk.Treeview(prod_plan_frame, columns=("product", "day", "qty"), show="headings", height=8)
        self.prod_tree.heading("product", text="Product")
        self.prod_tree.heading("day", text="Day")
        self.prod_tree.heading("qty", text="Quantity")
        self.prod_tree.column("product", width=100, anchor="center")
        self.prod_tree.column("day", width=80, anchor="center")
        self.prod_tree.column("qty", width=100, anchor="center")
        self.prod_tree.pack(fill="x", padx=10, pady=5)

        # Buttons frame
        btn_frame = ttk.Frame(setup_notebook)
        setup_notebook.add(btn_frame, text="Actions")
        
        ttk.Button(btn_frame, text="Run Simulation", command=self.run_simulation).pack(pady=20)
        ttk.Button(btn_frame, text="Optimize Production", command=self.optimize_production).pack(pady=20)
        ttk.Button(btn_frame, text="Export Original Results", command=self.export_original_results).pack(pady=20)
        ttk.Button(btn_frame, text="Export Optimized Plan", command=self.export_optimized_plan).pack(pady=20)
        ttk.Button(btn_frame, text="Export All", command=self.export_all).pack(pady=20)

        # === RESULTS TAB ===
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="Results")

        results_notebook = ttk.Notebook(results_frame)
        results_notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.purchases_table = self._create_tab(results_notebook, "Purchases")
        self.waste_table = self._create_tab(results_notebook, "Waste")
        self.batch_table = self._create_tab(results_notebook, "Batch Purchases")
        self.inventory_table = self._create_tab(results_notebook, "Daily Inventory")
        self.optimization_table = self._create_tab(results_notebook, "Optimization")

        viz_frame = ttk.Frame(results_notebook)
        results_notebook.add(viz_frame, text="Charts")
        self.viz_canvas = None
        self.viz_frame = viz_frame
        
        self.update_ui()

    def _create_tab(self, parent, title):
        frame = ttk.Frame(parent)
        parent.add(frame, text=title)
        tree = ttk.Treeview(frame, show="headings")
        tree.pack(fill="both", expand=True, padx=5, pady=5)
        vsb = ttk.Scrollbar(tree, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(tree, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        setattr(self, f"{title.lower().replace(' ', '_')}_table", tree)
        return tree

    def update_theme_button_text(self):
        """Update the theme button text based on current mode"""
        if hasattr(self, 'theme_btn'):
            self.theme_btn.config(text="☀️ Light Mode" if self.is_dark_mode else "🌙 Dark Mode")

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.colors = self._get_colors()
        self.update_theme_button_text()
        # Recreate the entire UI with new theme
        for widget in self.root.winfo_children():
            widget.destroy()
        self.create_widgets()

    def update_ui(self):
        # Update product combo box
        self.prod_combo['values'] = list(self.products.keys())
        if self.products:
            self.prod_combo.set(list(self.products.keys())[0])
        
        # Update product checkboxes
        for var in self.prod_vars:
            var.set(False)
        self.prod_vars.clear()
        self.prod_checkboxes.clear()
        
        for widget in self.prod_selection_frame.winfo_children()[1:]:
            widget.destroy()
            
        for i, prod_name in enumerate(self.products.keys()):
            var = tk.BooleanVar()
            self.prod_vars.append(var)
            cb = ttk.Checkbutton(self.prod_selection_frame, text=prod_name, variable=var)
            cb.grid(row=i//5 + 1, column=i%5, sticky="w", padx=5, pady=2)
            self.prod_checkboxes.append(cb)

        # Update product listbox
        self.prod_listbox.delete(0, tk.END)
        for prod_name, data in self.products.items():
            self.prod_listbox.insert(tk.END, f"{prod_name} (SL={data['shelf_life']})")

        # Update distributor listbox
        self.dist_listbox.delete(0, tk.END)
        for dist in self.distributors:
            self.dist_listbox.insert(tk.END, f"{dist['name']} (Policy={dist['policy_days']}, Products={len(dist['preferred_products'])})")

    def add_product(self):
        name = self.prod_name_var.get().strip()
        sl_text = self.prod_shelf_life_var.get().strip()
        if not name or not sl_text:
            return messagebox.showwarning("Input", "Enter name and shelf life.")
        try:
            sl = int(sl_text)
            if sl <= 0:
                raise ValueError("Shelf life must be positive")
        except:
            return messagebox.showerror("Error", "Shelf life must be a positive integer.")
            
        self.products[name] = {'shelf_life': sl, 'production_plan': {}}
        self.prod_name_var.set("")
        self.prod_shelf_life_var.set("")
        self.update_ui()

    def remove_product(self):
        sel = self.prod_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        item_text = self.prod_listbox.get(idx)
        prod_name = item_text.split()[0]
        self.prod_listbox.delete(idx)
        if prod_name in self.products:
            del self.products[prod_name]
        self.update_ui()

    def add_distributor(self):
        name = self.dist_name_var.get().strip()
        policy_text = self.dist_policy_var.get().strip()
        prop_text = self.dist_prop_var.get().strip()
        dist_text = self.dist_dist_var.get().strip()
        
        if not name or not policy_text or not prop_text or not dist_text:
            return messagebox.showwarning("Input", "Fill all fields.")
            
        try:
            policy = int(policy_text)
            prop = float(prop_text)
            distance = int(dist_text)
            if policy <= 0 or prop <= 0 or prop > 1 or distance <= 0:
                raise ValueError("Invalid values")
        except:
            return messagebox.showerror("Error", "Invalid numeric values.")
            
        # Get selected products
        selected_products = []
        for i, var in enumerate(self.prod_vars):
            if var.get():
                selected_products.append(list(self.products.keys())[i])
                
        if not selected_products:
            return messagebox.showwarning("Selection", "Select at least one product for this distributor.")
            
        # Create purchase_days array for full simulation period
        purchase_days = [var.get() for var in self.day_vars]  # Weekly pattern
        full_purchase_days = []
        for day in range(1, self.sim_days.get() + 1):
            weekday_index = (day - 1) % 7  # 0=Mon, 1=Tue, ..., 6=Sun
            full_purchase_days.append(purchase_days[weekday_index])
            
        self.distributors.append({
            'name': name,
            'policy_days': policy,
            'proportion': round(prop, 2),
            'distance_km': distance,
            'purchase_days': full_purchase_days,
            'preferred_products': selected_products
        })
        
        self.dist_name_var.set("")
        self.dist_policy_var.set("1")
        self.dist_prop_var.set("0.15")
        self.dist_dist_var.set("10")
        for var in self.prod_vars:
            var.set(False)
        for var in self.day_vars:
            var.set(True if self.day_vars.index(var) < 6 else False)  # Reset to default (Mon-Sat)
            
        self.update_ui()

    def remove_distributor(self):
        sel = self.dist_listbox.curselection()
        if not sel:
            return
        self.dist_listbox.delete(sel[0])
        if sel[0] < len(self.distributors):
            del self.distributors[sel[0]]
        self.update_ui()

    def add_production(self):
        try:
            prod_name = self.prod_var.get()
            day_text = self.prod_day_var.get().strip()
            qty_text = self.prod_qty_var.get().strip()
            
            if not prod_name:
                return messagebox.showwarning("Select", "Choose a product.")
            if not day_text or not qty_text:
                return messagebox.showwarning("Input", "Enter day and quantity.")
                
            day = int(day_text)
            qty = float(qty_text)
            
            if day < 1 or qty < 0:
                raise ValueError("Invalid input")
            if prod_name not in self.products:
                return messagebox.showerror("Error", "Product not found.")
                
            self.products[prod_name]['production_plan'][day] = qty
            self.prod_tree.insert("", "end", values=(prod_name, day, int(qty)))
            self.prod_day_var.set("")
            self.prod_qty_var.set("")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def remove_production(self):
        selected = self.prod_tree.selection()
        for item in selected:
            values = self.prod_tree.item(item, "values")
            prod_name, day = values[0], int(values[1])
            if prod_name in self.products and day in self.products[prod_name]['production_plan']:
                del self.products[prod_name]['production_plan'][day]
            self.prod_tree.delete(item)

    def run_simulation(self):
        if not self.products:
            return messagebox.showerror("Error", "Add at least one product.")
        for p, data in self.products.items():
            if not data['production_plan']:
                return messagebox.showerror("Error", f"Add production for {p}.")
        if not self.distributors:
            return messagebox.showerror("Error", "Add at least one distributor.")

        model = PerishableSupplyChain(
            products=self.products,
            distributors=self.distributors,
            transport_rate=self.transport_rate.get(),
            sim_days_override=self.sim_days.get()
        )

        try:
            self.all_results = model.run_simulation()
            self.display_results()
            messagebox.showinfo("Success", "Simulation completed successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Simulation failed: {str(e)}")

    def display_results(self):
        # Combine all purchases
        all_purchases = []
        for prod, data in self.all_results.items():
            df = data['purchases']
            if not df.empty:
                all_purchases.append(df)
        if all_purchases:
            full_purchases = pd.concat(all_purchases, ignore_index=True)
            self._populate_table(self.purchases_table, full_purchases)
        else:
            self._clear_table(self.purchases_table)

        # Combine all waste
        all_waste = pd.concat([data['waste'] for data in self.all_results.values()], ignore_index=True)
        self._populate_table(self.waste_table, all_waste)

        # First product's batch pivot
        if self.all_results:
            first_prod = list(self.all_results.keys())[0]
            df = self.all_results[first_prod]['batch_pivot']
            if not df.empty:
                self._populate_table(self.batch_table, df.reset_index())
            else:
                self._clear_table(self.batch_table)

            inv_log = self.all_results[first_prod]['inventory_log']
            self._populate_table(self.inventory_table, inv_log)

        self._plot_results()

    def optimize_production(self):
        """Generate optimized production plan using LP"""
        if not self.products or not self.distributors:
            return messagebox.showwarning("Setup", "Add products and distributors first.")
            
        try:
            # Use first product for optimization
            first_prod = list(self.products.keys())[0]
            shelf_life = self.products[first_prod]['shelf_life']
            sim_days = self.sim_days.get()
            
            model = PerishableSupplyChain(
                products=self.products,
                distributors=self.distributors,
                transport_rate=self.transport_rate.get(),
                sim_days_override=sim_days
            )
            
            rec = model.optimize_production(sim_days, shelf_life)
            self.optimized_production = {first_prod: rec}
            
            lp_df = pd.DataFrame(list(rec.items()), columns=["Day", "Recommended Production"])
            self._populate_table(self.optimization_table, lp_df)
            
            messagebox.showinfo("Optimization", "Production optimization completed!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Optimization failed: {str(e)}")

    def _populate_table(self, table, df):
        self._clear_table(table)
        if df.empty:
            return
        table["columns"] = list(df.columns)
        for col in df.columns:
            table.heading(col, text=col)
            table.column(col, width=80, anchor="center")
        for _, row in df.iterrows():
            table.insert("", "end", values=[round(v, 2) if isinstance(v, float) else v for v in row])

    def _clear_table(self, table):
        for item in table.get_children():
            table.delete(item)

    def _plot_results(self):
        if self.viz_canvas:
            self.viz_canvas.get_tk_widget().destroy()

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle("Simulation Results", fontsize=14)

        # Waste by batch
        all_waste = pd.concat([data['waste'] for data in self.all_results.values()], ignore_index=True)
        axes[0, 0].bar(all_waste['Batch_Day'], all_waste['Waste'], color='orangered')
        axes[0, 0].set_title("Waste by Batch")
        axes[0, 0].set_xlabel("Production Day")

        # Waste distribution
        axes[0, 1].pie(all_waste['Waste'], labels=all_waste['Batch_Day'], autopct='%1.1f%%')
        axes[0, 1].set_title("Waste Distribution (%)")

        # Total purchases by product
        if not all_waste.empty:
            prod_sum = all_waste.groupby('Product')['Initial'].sum() - all_waste.groupby('Product')['Waste'].sum()
            axes[1, 0].bar(prod_sum.index, prod_sum.values, color='teal')
            axes[1, 0].set_title("Total Sales per Product")

        # Batch purchases
        if self.all_results:
            first_prod = list(self.all_results.keys())[0]
            batch = self.all_results[first_prod]['batch_pivot']
            if not batch.empty:
                batch.T.plot(kind='bar', ax=axes[1, 1], legend=False)
                axes[1, 1].set_title("Batch Purchases")

        plt.tight_layout()
        self.viz_canvas = FigureCanvasTkAgg(fig, self.viz_frame)
        self.viz_canvas.draw()
        self.viz_canvas.get_tk_widget().pack(fill="both", expand=True)

    def export_original_results(self):
        if not self.all_results:
            return messagebox.showwarning("No Data", "Run simulation first.")

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Export Original Results"
        )
        if not file_path:
            return

        self._export_to_excel(file_path, include_optimized=False)
        messagebox.showinfo("Export Success", f"Original results exported to:\n{os.path.basename(file_path)}")

    def export_optimized_plan(self):
        if not hasattr(self, 'optimized_production') or not self.optimized_production:
            return messagebox.showwarning("No Data", "Run optimization first.")

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Export Optimized Production Plan"
        )
        if not file_path:
            return

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            for prod_name, plan in self.optimized_production.items():
                df = pd.DataFrame(list(plan.items()), columns=["Day", "Recommended Quantity"])
                df.to_excel(writer, sheet_name=f"{prod_name}_Optimized", index=False)

        messagebox.showinfo("Export Success", f"Optimized plan exported to:\n{os.path.basename(file_path)}")

    def export_all(self):
        if not self.all_results:
            return messagebox.showwarning("No Data", "Run simulation first.")

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Export All Results"
        )
        if not file_path:
            return

        self._export_to_excel(file_path, include_optimized=True)
        messagebox.showinfo("Export Success", f"All results exported to:\n{os.path.basename(file_path)}")

    def _export_to_excel(self, file_path, include_optimized=True):
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # Purchases
            all_purchases = []
            for prod, data in self.all_results.items():
                df = data['purchases']
                if not df.empty:
                    all_purchases.append(df)
            if all_purchases:
                pd.concat(all_purchases, ignore_index=True).to_excel(writer, sheet_name='Purchases', index=False)

            # Waste
            all_waste = pd.concat([data['waste'] for data in self.all_results.values()], ignore_index=True)
            all_waste.to_excel(writer, sheet_name='Waste Summary', index=False)

            # Batch pivots
            for prod, data in self.all_results.items():
                if not data['batch_pivot'].empty:
                    data['batch_pivot'].to_excel(writer, sheet_name=f'Batch_{prod}', index=True)

            # Inventory logs
            for prod, data in self.all_results.items():
                data['inventory_log'].to_excel(writer, sheet_name=f'Inventory_{prod}', index=False)

            # Financial summary
            total_revenue = 0
            total_production_cost = 0
            total_transport_cost = sum(p['purchases']['Transport_Cost'].sum() 
                                     for p in self.all_results.values())
            
            summary_data = [{
                'Metric': ['Total Transport Cost', 'Simulation Days'],
                'Value': [
                    f"{total_transport_cost:.2f}",
                    self.sim_days.get()
                ]
            }]
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

            # Optimized production if requested
            if include_optimized and hasattr(self, 'optimized_production'):
                for prod_name, plan in self.optimized_production.items():
                    df = pd.DataFrame(list(plan.items()), columns=["Day", "Recommended Quantity"])
                    df.to_excel(writer, sheet_name=f"Optimal_{prod_name}", index=False)


def main():
    root = tk.Tk()
    app = SupplyChainApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()