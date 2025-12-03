# Perishable Supply Chain Enterprise Optimizer

## Overview

A comprehensive, market-ready application for optimizing perishable product distribution in multi-distributor supply chains. This enterprise-grade solution implements the mathematical model from Orsarh et al. (2024) with advanced features for real-world deployment.

## Features

### Core Functionality
- **Multi-Product Support**: Manage different perishable products with unique shelf lives
- **Distributor Product Preferences**: Distributors can select which products to purchase
- **Policy-Based Distribution**: Implements precedence relationships and age-based purchasing policies
- **Accurate Waste Modeling**: Products expire after shelf life period; waste tracked by batch

### Advanced Optimization
- **Production Optimization**: LP-based recommendation engine minimizes waste
- **Transport Cost Integration**: Full cost modeling including transportation expenses
- **Profit Maximization**: Objective function aligns with business goals

### User Experience
- **Modern Dark/Light Mode Toggle**: Professional appearance with user preference options
- **Modular Interface Design**: Intuitive sectioning of functionality
- **Responsive Layout**: Clean, attractive GUI suitable for enterprise use
- **Comprehensive Export Options**: All results exportable to Excel with financial analysis

### Enterprise Capabilities
- **Batch Processing**: Handle multiple products and distributors simultaneously
- **Data Validation**: Robust input checking and error handling
- **Audit Trail**: Complete record of all simulations and optimizations
- **Scalable Architecture**: Designed for integration into larger supply chain systems

## Installation

```bash
git clone https://https://github.com/CaptHwi1/Supply-chain-Optimizer.git
cd Supply-chain-Optimizer.git

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Requirements:**
- Python 3.8+
- pandas
- pulp
- matplotlib
- openpyxl
- tkinter

## Usage

1. **Launch Application**
```bash
python main.py
```

2. **Configure Products**
   - Add multiple products with different shelf lives
   - Set selling price, production cost, and other parameters

3. **Setup Distributors**
   - Define distributor network with policy days and purchase proportions
   - Assign product preferences to each distributor
   - Configure weekly purchase schedules

4. **Production Planning**
   - Enter current production quantities
   - Run simulation to analyze waste and performance
   - Generate optimized production recommendations

5. **Export Results**
   - Export original simulation results
   - Export optimized production plan
   - Comprehensive financial reports

## Interface Sections

### 1. Product Management Module
- Add/edit/delete products
- Configure shelf life and financial parameters
- View product-specific analytics

### 2. Distributor Configuration Module  
- Create distributor profiles
- Set policy days (1-30)
- Define purchase proportions (1-100%)
- Select preferred products
- Configure weekly availability

### 3. Production Planning Module
- Input daily production quantities
- Visualize capacity utilization
- Compare actual vs optimal production

### 4. Simulation & Optimization Engine
- Run detailed day-by-day simulation
- Generate LP-based optimization recommendations
- Compare scenarios side-by-side

### 5. Reporting & Export Module
- Interactive charts and visualizations
- Detailed waste analysis
- Financial performance metrics
- Multi-sheet Excel exports

## Data Model

### Products
- Unique identifier
- Name
- Shelf life (days)
- Selling price
- Production cost
- Current production plan

### Distributors
- Unique identifier
- Name
- Policy days (acceptance window)
- Purchase proportion
- Distance from manufacturer
- Preferred products
- Weekly purchase schedule

### Transactions
- Batch tracking by production day
- Purchase records with timestamps
- Waste logging at expiration
- Inventory levels throughout cycle

## Optimization Algorithm

The LP optimization engine maximizes profit using the objective function:
```
Maximize Z = Σ(bj − cj − rjQj − dj) * Total_Purchase
```

Where:
- bj = Selling price per unit
- cj = Production cost per unit  
- rj = Holding cost coefficient
- dj = Transport cost per unit
- Qj = Production quantity

Subject to plant storage capacity constraints derived from the 4-day production cycle.

## Export Capabilities

All data is exportable to Excel workbooks containing:

**Original Simulation Results:**
- Purchases by distributor and batch
- Waste analysis by production day
- Distributor performance summary
- Daily inventory logs
- Batch purchase breakdown

**Optimized Production Plan:**
- Recommended daily production quantities
- Projected waste reduction
- Expected cost savings
- Capacity utilization forecast

**Financial Analysis:**
- Revenue projections
- Cost breakdown (production, transport, waste)
- Profit margins
- Key performance indicators

## Configuration Options

- Dark/light theme toggle
- Customizable simulation duration (1-365 days)
- Adjustable transport rates
- Configurable allowable waste thresholds
- Flexible distributor precedence rules



## Support

For technical support, documentation, or enterprise deployment assistance, contact abdulmuiz0a@gmail.com.

---

*Perishable Supply Chain Enterprise Optimizer - Version 1.0.0*
