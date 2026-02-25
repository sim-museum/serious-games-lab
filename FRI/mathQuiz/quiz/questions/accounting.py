"""
Accounting question generators.

Questions based on Martin Kleppmann's "Accounting for Computer Scientists" blog post.
Uses graph theory concepts to explain double-entry bookkeeping.
Higher point value advanced questions with graphical augmentation.

Key concepts:
- Accounts = Nodes, Transactions = Edges
- Double-entry: every transaction affects two accounts
- Assets = Liabilities + Equity (accounting equation)
- Profit = Revenue - Expenses
"""

import numpy as np
from typing import List, Tuple, Dict

from .base import Question, QuestionGenerator, QuestionCategory
from ..difficulty import DifficultyLevel


class AccountingEquationQuestion(QuestionGenerator):
    """Generate questions about the fundamental accounting equation."""

    CATEGORY = QuestionCategory.ACCOUNTING
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.MEDIUM)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.EASY:
            # Basic accounting equation: Assets = Liabilities + Equity
            choice = np.random.randint(0, 3)

            if choice == 0:
                # Find assets
                liabilities = np.random.randint(5, 50) * 1000
                equity = np.random.randint(10, 100) * 1000
                answer = liabilities + equity

                text = f"A company has liabilities of ${liabilities:,} and equity of ${equity:,}.\nWhat are the total assets?"
                explanation = f"Assets = Liabilities + Equity = ${liabilities:,} + ${equity:,} = ${answer:,}"

            elif choice == 1:
                # Find liabilities
                assets = np.random.randint(50, 200) * 1000
                equity = np.random.randint(20, assets // 1000 - 10) * 1000
                answer = assets - equity

                text = f"A company has assets of ${assets:,} and equity of ${equity:,}.\nWhat are the total liabilities?"
                explanation = f"Liabilities = Assets - Equity = ${assets:,} - ${equity:,} = ${answer:,}"

            else:
                # Find equity
                assets = np.random.randint(50, 200) * 1000
                liabilities = np.random.randint(10, assets // 1000 - 20) * 1000
                answer = assets - liabilities

                text = f"A company has assets of ${assets:,} and liabilities of ${liabilities:,}.\nWhat is the total equity?"
                explanation = f"Equity = Assets - Liabilities = ${assets:,} - ${liabilities:,} = ${answer:,}"

            latex = "\\text{Assets} = \\text{Liabilities} + \\text{Equity}"
            hint = "Use the accounting equation: Assets = Liabilities + Equity"

            # Balance sheet visualization
            plot_data = {
                'accounting_equation': True,
                'title': "The Accounting Equation"
            }

        else:  # MEDIUM
            # After a transaction, verify the equation still balances
            initial_assets = np.random.randint(50, 100) * 1000
            initial_liabilities = np.random.randint(10, 30) * 1000
            initial_equity = initial_assets - initial_liabilities

            # Transaction types
            trans_type = np.random.randint(0, 3)

            if trans_type == 0:
                # Borrow money (increases assets and liabilities)
                loan = np.random.randint(5, 20) * 1000
                new_assets = initial_assets + loan
                new_liabilities = initial_liabilities + loan
                answer = new_assets

                text = f"A company starts with:\n- Assets: ${initial_assets:,}\n- Liabilities: ${initial_liabilities:,}\n- Equity: ${initial_equity:,}\n\nThey take a bank loan of ${loan:,}.\nWhat are the new total assets?"
                explanation = f"Borrowing increases both assets (cash) and liabilities.\nNew Assets = ${initial_assets:,} + ${loan:,} = ${answer:,}"

            elif trans_type == 1:
                # Owner investment (increases assets and equity)
                investment = np.random.randint(10, 30) * 1000
                new_assets = initial_assets + investment
                new_equity = initial_equity + investment
                answer = new_equity

                text = f"A company starts with:\n- Assets: ${initial_assets:,}\n- Liabilities: ${initial_liabilities:,}\n- Equity: ${initial_equity:,}\n\nThe owner invests ${investment:,} in cash.\nWhat is the new total equity?"
                explanation = f"Owner investment increases both assets and equity.\nNew Equity = ${initial_equity:,} + ${investment:,} = ${answer:,}"

            else:
                # Pay off debt (decreases assets and liabilities)
                payment = min(initial_liabilities, np.random.randint(5, 15) * 1000)
                new_assets = initial_assets - payment
                new_liabilities = initial_liabilities - payment
                answer = new_liabilities

                text = f"A company starts with:\n- Assets: ${initial_assets:,}\n- Liabilities: ${initial_liabilities:,}\n- Equity: ${initial_equity:,}\n\nThey pay off ${payment:,} of debt.\nWhat are the new total liabilities?"
                explanation = f"Paying debt decreases both assets (cash) and liabilities.\nNew Liabilities = ${initial_liabilities:,} - ${payment:,} = ${answer:,}"

            latex = "\\text{Assets} = \\text{Liabilities} + \\text{Equity}"
            hint = "Think about which accounts are affected by the transaction."
            plot_data = None

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric",
            plot_data=plot_data,
            requires_plot=plot_data is not None
        )


class DoubleEntryQuestion(QuestionGenerator):
    """Generate questions about double-entry bookkeeping principles."""

    CATEGORY = QuestionCategory.ACCOUNTING
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.MEDIUM:
            # Identify which accounts are affected
            transactions = [
                {
                    'description': "A customer pays $500 cash for a product",
                    'debit': 'Cash (Asset)',
                    'credit': 'Revenue',
                    'amount': 500,
                    'answer': 'Cash increases, Revenue increases'
                },
                {
                    'description': "The company buys $1,000 of equipment on credit",
                    'debit': 'Equipment (Asset)',
                    'credit': 'Accounts Payable (Liability)',
                    'amount': 1000,
                    'answer': 'Equipment increases, Accounts Payable increases'
                },
                {
                    'description': "The company pays $300 for office rent",
                    'debit': 'Rent Expense',
                    'credit': 'Cash (Asset)',
                    'amount': 300,
                    'answer': 'Rent Expense increases, Cash decreases'
                },
                {
                    'description': "A founder invests $5,000 in the company",
                    'debit': 'Cash (Asset)',
                    'credit': 'Equity',
                    'amount': 5000,
                    'answer': 'Cash increases, Equity increases'
                },
            ]

            trans = transactions[np.random.randint(len(transactions))]
            amount = trans['amount']
            answer = amount  # The amount that flows

            text = f"In double-entry bookkeeping:\n{trans['description']}\n\nHow much is recorded as a debit to {trans['debit'].split()[0]}?"
            latex = ""
            explanation = f"This transaction: {trans['answer']}.\nDebit {trans['debit']}: ${amount}, Credit {trans['credit']}: ${amount}"
            hint = "In double-entry, every transaction has equal debits and credits."

            # Transaction flow diagram
            plot_data = {
                'transaction_flow': (trans['debit'], trans['credit'], amount),
                'title': "Double-Entry Transaction"
            }

        else:  # HARD
            # Calculate account balance after multiple transactions
            transactions = []
            cash_balance = np.random.randint(5, 20) * 1000  # Starting cash

            n_trans = np.random.randint(3, 5)
            for _ in range(n_trans):
                trans_type = np.random.choice(['sale', 'expense', 'payment_received'])
                if trans_type == 'sale':
                    amount = np.random.randint(1, 10) * 100
                    transactions.append(f"Cash sale: +${amount}")
                    cash_balance += amount
                elif trans_type == 'expense':
                    amount = np.random.randint(1, 8) * 100
                    transactions.append(f"Expense paid: -${amount}")
                    cash_balance -= amount
                else:
                    amount = np.random.randint(5, 15) * 100
                    transactions.append(f"Customer payment: +${amount}")
                    cash_balance += amount

            answer = cash_balance
            trans_list = '\n'.join([f"  {i+1}. {t}" for i, t in enumerate(transactions)])

            text = f"Starting cash balance: ${cash_balance - sum([int(t.split('$')[1]) if '+' in t else -int(t.split('$')[1]) for t in transactions]):,}\n\nTransactions:\n{trans_list}\n\nWhat is the ending cash balance?"
            latex = ""
            explanation = f"Apply each transaction to the starting balance.\nFinal Cash Balance: ${answer:,}"
            hint = "Track how each transaction affects the cash account."
            plot_data = None

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric",
            plot_data=plot_data,
            requires_plot=plot_data is not None
        )


class ProfitLossQuestion(QuestionGenerator):
    """Generate questions about profit and loss calculations."""

    CATEGORY = QuestionCategory.ACCOUNTING
    DIFFICULTY_RANGE = (DifficultyLevel.EASY, DifficultyLevel.HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.EASY:
            # Simple profit calculation
            revenue = np.random.randint(10, 50) * 1000
            expenses = np.random.randint(5, revenue // 1000 - 2) * 1000
            answer = revenue - expenses

            text = f"A company has:\n- Total Revenue: ${revenue:,}\n- Total Expenses: ${expenses:,}\n\nWhat is the profit (or loss)?"
            latex = "\\text{Profit} = \\text{Revenue} - \\text{Expenses}"
            explanation = f"Profit = ${revenue:,} - ${expenses:,} = ${answer:,}"
            hint = "Profit = Revenue - Expenses"

            # P&L visualization
            plot_data = {
                'profit_loss': (revenue, expenses),
                'title': "Profit & Loss"
            }

        elif difficulty == DifficultyLevel.MEDIUM:
            # Multiple revenue and expense categories
            sales_revenue = np.random.randint(20, 60) * 1000
            service_revenue = np.random.randint(5, 20) * 1000

            cost_of_goods = np.random.randint(10, 30) * 1000
            salaries = np.random.randint(5, 15) * 1000
            rent = np.random.randint(2, 8) * 1000
            utilities = np.random.randint(1, 5) * 100

            total_revenue = sales_revenue + service_revenue
            total_expenses = cost_of_goods + salaries + rent + utilities
            answer = total_revenue - total_expenses

            text = f"""Calculate the net profit given:

Revenue:
- Sales: ${sales_revenue:,}
- Services: ${service_revenue:,}

Expenses:
- Cost of goods sold: ${cost_of_goods:,}
- Salaries: ${salaries:,}
- Rent: ${rent:,}
- Utilities: ${utilities:,}"""

            latex = ""
            explanation = f"Total Revenue: ${total_revenue:,}\nTotal Expenses: ${total_expenses:,}\nNet Profit: ${answer:,}"
            hint = "Sum all revenues, sum all expenses, then subtract."

            plot_data = {
                'profit_loss_detailed': {
                    'revenue': [('Sales', sales_revenue), ('Services', service_revenue)],
                    'expenses': [('COGS', cost_of_goods), ('Salaries', salaries), ('Rent', rent), ('Utilities', utilities)]
                },
                'title': "Detailed P&L Statement"
            }

        else:  # HARD
            # Gross margin and operating margin
            revenue = np.random.randint(50, 150) * 1000
            cogs = np.random.randint(20, 60) * 1000  # Cost of goods sold
            operating_expenses = np.random.randint(10, 40) * 1000

            gross_profit = revenue - cogs
            operating_profit = gross_profit - operating_expenses

            choice = np.random.randint(0, 2)
            if choice == 0:
                # Gross margin percentage
                answer = round((gross_profit / revenue) * 100, 1)
                text = f"A company has:\n- Revenue: ${revenue:,}\n- Cost of Goods Sold: ${cogs:,}\n\nWhat is the gross margin percentage?\n(Round to 1 decimal place)"
                explanation = f"Gross Profit = ${revenue:,} - ${cogs:,} = ${gross_profit:,}\nGross Margin = (${gross_profit:,} / ${revenue:,}) × 100 = {answer}%"
                hint = "Gross Margin % = (Gross Profit / Revenue) × 100"
            else:
                # Operating margin percentage
                answer = round((operating_profit / revenue) * 100, 1)
                text = f"A company has:\n- Revenue: ${revenue:,}\n- Cost of Goods Sold: ${cogs:,}\n- Operating Expenses: ${operating_expenses:,}\n\nWhat is the operating margin percentage?\n(Round to 1 decimal place)"
                explanation = f"Operating Profit = ${gross_profit:,} - ${operating_expenses:,} = ${operating_profit:,}\nOperating Margin = (${operating_profit:,} / ${revenue:,}) × 100 = {answer}%"
                hint = "Operating Margin % = (Operating Profit / Revenue) × 100"

            latex = ""
            plot_data = None

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric",
            tolerance=0.05,
            plot_data=plot_data,
            requires_plot=plot_data is not None
        )


class BalanceSheetQuestion(QuestionGenerator):
    """Generate questions about balance sheet analysis."""

    CATEGORY = QuestionCategory.ACCOUNTING
    DIFFICULTY_RANGE = (DifficultyLevel.MEDIUM, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.MEDIUM:
            # Classify accounts as Assets, Liabilities, or Equity
            accounts = [
                ('Cash', 'Asset'),
                ('Accounts Receivable', 'Asset'),
                ('Inventory', 'Asset'),
                ('Equipment', 'Asset'),
                ('Accounts Payable', 'Liability'),
                ('Bank Loan', 'Liability'),
                ('Wages Payable', 'Liability'),
                ('Owner\'s Capital', 'Equity'),
                ('Retained Earnings', 'Equity'),
            ]

            # Pick random accounts and ask to sum a category
            selected = np.random.choice(len(accounts), size=5, replace=False)
            account_values = {}
            for idx in selected:
                name, category = accounts[idx]
                value = np.random.randint(1, 20) * 1000
                account_values[name] = (value, category)

            target_category = np.random.choice(['Asset', 'Liability', 'Equity'])
            answer = sum(v for (v, c) in account_values.values() if c == target_category)

            account_list = '\n'.join([f"  - {name}: ${val:,}" for name, (val, _) in account_values.items()])
            text = f"Given these accounts:\n{account_list}\n\nWhat is the total of all {target_category}s?"
            latex = ""
            explanation = f"Sum of {target_category}s: ${answer:,}"
            hint = f"Identify which accounts are {target_category}s and sum them."
            plot_data = None

        elif difficulty == DifficultyLevel.HARD:
            # Calculate working capital or current ratio
            current_assets = {
                'Cash': np.random.randint(5, 20) * 1000,
                'Accounts Receivable': np.random.randint(3, 15) * 1000,
                'Inventory': np.random.randint(5, 25) * 1000,
            }
            current_liabilities = {
                'Accounts Payable': np.random.randint(3, 12) * 1000,
                'Short-term Debt': np.random.randint(2, 10) * 1000,
            }

            total_ca = sum(current_assets.values())
            total_cl = sum(current_liabilities.values())

            choice = np.random.randint(0, 2)
            if choice == 0:
                # Working capital
                answer = total_ca - total_cl
                text = f"""Calculate working capital:

Current Assets:
{chr(10).join([f'  - {k}: ${v:,}' for k, v in current_assets.items()])}

Current Liabilities:
{chr(10).join([f'  - {k}: ${v:,}' for k, v in current_liabilities.items()])}"""
                explanation = f"Working Capital = Current Assets - Current Liabilities\n= ${total_ca:,} - ${total_cl:,} = ${answer:,}"
                hint = "Working Capital = Current Assets - Current Liabilities"
            else:
                # Current ratio
                answer = round(total_ca / total_cl, 2)
                text = f"""Calculate the current ratio:

Current Assets:
{chr(10).join([f'  - {k}: ${v:,}' for k, v in current_assets.items()])}

Current Liabilities:
{chr(10).join([f'  - {k}: ${v:,}' for k, v in current_liabilities.items()])}

(Round to 2 decimal places)"""
                explanation = f"Current Ratio = Current Assets / Current Liabilities\n= ${total_ca:,} / ${total_cl:,} = {answer}"
                hint = "Current Ratio = Current Assets / Current Liabilities"

            latex = ""
            plot_data = {
                'balance_comparison': (total_ca, total_cl),
                'title': "Current Assets vs Liabilities"
            }

        else:  # VERY_HARD
            # Complete balance sheet reconciliation
            # Assets
            cash = np.random.randint(5, 20) * 1000
            receivables = np.random.randint(5, 15) * 1000
            inventory = np.random.randint(10, 30) * 1000
            equipment = np.random.randint(20, 50) * 1000
            total_assets = cash + receivables + inventory + equipment

            # Liabilities
            payables = np.random.randint(5, 15) * 1000
            debt = np.random.randint(10, 30) * 1000
            total_liabilities = payables + debt

            # Equity (must balance)
            equity = total_assets - total_liabilities

            # Ask for missing value
            choice = np.random.randint(0, 4)
            if choice == 0:
                hidden = 'Cash'
                answer = cash
                text_assets = f"  - Cash: ?\n  - Accounts Receivable: ${receivables:,}\n  - Inventory: ${inventory:,}\n  - Equipment: ${equipment:,}"
            elif choice == 1:
                hidden = 'Equipment'
                answer = equipment
                text_assets = f"  - Cash: ${cash:,}\n  - Accounts Receivable: ${receivables:,}\n  - Inventory: ${inventory:,}\n  - Equipment: ?"
            elif choice == 2:
                hidden = 'Total Liabilities'
                answer = total_liabilities
                text_assets = f"  - Cash: ${cash:,}\n  - Accounts Receivable: ${receivables:,}\n  - Inventory: ${inventory:,}\n  - Equipment: ${equipment:,}"
            else:
                hidden = 'Equity'
                answer = equity
                text_assets = f"  - Cash: ${cash:,}\n  - Accounts Receivable: ${receivables:,}\n  - Inventory: ${inventory:,}\n  - Equipment: ${equipment:,}"

            if choice < 2:
                text = f"""Find the missing value to balance the sheet:

Assets:
{text_assets}

Liabilities: ${total_liabilities:,}
Equity: ${equity:,}

What is {hidden}?"""
            elif choice == 2:
                text = f"""Find the missing value to balance the sheet:

Assets:
{text_assets}
Total Assets: ${total_assets:,}

Liabilities: ?
Equity: ${equity:,}

What are the Total Liabilities?"""
            else:
                text = f"""Find the missing value to balance the sheet:

Assets:
{text_assets}
Total Assets: ${total_assets:,}

Liabilities: ${total_liabilities:,}
Equity: ?

What is the Equity?"""

            latex = ""
            explanation = f"Using Assets = Liabilities + Equity:\n${total_assets:,} = ${total_liabilities:,} + ${equity:,}\n{hidden} = ${answer:,}"
            hint = "The accounting equation must balance: Assets = Liabilities + Equity"
            plot_data = None

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric",
            tolerance=0.01,
            plot_data=plot_data,
            requires_plot=plot_data is not None
        )


class GraphModelQuestion(QuestionGenerator):
    """Generate questions using Kleppmann's graph theory model of accounting."""

    CATEGORY = QuestionCategory.ACCOUNTING
    DIFFICULTY_RANGE = (DifficultyLevel.HARD, DifficultyLevel.VERY_HARD)

    def generate(self, difficulty: DifficultyLevel) -> Question:
        if difficulty == DifficultyLevel.HARD:
            # Sum of all account balances should be zero
            # Create a small ledger
            accounts = {
                'Cash': np.random.randint(-5, 20) * 1000,
                'Revenue': -np.random.randint(5, 30) * 1000,  # Revenue is negative in this model
                'Expenses': np.random.randint(5, 15) * 1000,
                'Equity': -np.random.randint(5, 20) * 1000,  # Equity is negative
            }

            # The sum must be zero, so adjust one account
            current_sum = sum(accounts.values())
            accounts['Accounts Payable'] = -current_sum  # This makes sum = 0

            # Hide one account
            hidden_key = np.random.choice(list(accounts.keys()))
            answer = accounts[hidden_key]

            visible = {k: v for k, v in accounts.items() if k != hidden_key}
            account_list = '\n'.join([f"  - {k}: ${v:,}" for k, v in visible.items()])

            text = f"""In the graph model of accounting, the sum of all account balances equals zero.

Known account balances:
{account_list}

What must be the balance of {hidden_key}?
(Positive = asset/expense, Negative = liability/revenue/equity)"""

            latex = "\\sum_{\\text{all accounts}} \\text{balance} = 0"
            explanation = f"Sum of visible accounts: ${sum(visible.values()):,}\n{hidden_key} must be ${answer:,} for the sum to equal zero."
            hint = "The sum of all accounts must be zero (double-entry principle)."
            plot_data = None

        else:  # VERY_HARD
            # Trace through a series of transactions
            initial_cash = 10000
            accounts = {
                'Cash': initial_cash,
                'Revenue': 0,
                'Expenses': 0,
                'Accounts Receivable': 0,
                'Equity': -initial_cash,  # Initial investment
            }

            transactions = []
            # Generate 3-4 transactions
            for _ in range(np.random.randint(3, 5)):
                t_type = np.random.choice(['sale_cash', 'sale_credit', 'expense', 'collect'])

                if t_type == 'sale_cash':
                    amount = np.random.randint(1, 10) * 1000
                    accounts['Cash'] += amount
                    accounts['Revenue'] -= amount
                    transactions.append(f"Cash sale: ${amount:,}")

                elif t_type == 'sale_credit':
                    amount = np.random.randint(1, 8) * 1000
                    accounts['Accounts Receivable'] += amount
                    accounts['Revenue'] -= amount
                    transactions.append(f"Credit sale: ${amount:,}")

                elif t_type == 'expense':
                    amount = np.random.randint(500, 5000)
                    accounts['Cash'] -= amount
                    accounts['Expenses'] += amount
                    transactions.append(f"Paid expense: ${amount:,}")

                elif t_type == 'collect' and accounts['Accounts Receivable'] > 0:
                    amount = min(accounts['Accounts Receivable'], np.random.randint(1, 5) * 1000)
                    accounts['Cash'] += amount
                    accounts['Accounts Receivable'] -= amount
                    transactions.append(f"Collected receivable: ${amount:,}")

            # Ask for final balance of one account
            target = np.random.choice(['Cash', 'Revenue', 'Expenses'])
            answer = accounts[target]
            if target == 'Revenue':
                answer = -answer  # Display positive revenue

            trans_list = '\n'.join([f"  {i+1}. {t}" for i, t in enumerate(transactions)])

            text = f"""Starting with ${initial_cash:,} in cash (from equity investment):

Transactions:
{trans_list}

What is the final {'total revenue' if target == 'Revenue' else target + ' balance'}?
{'(Enter as positive number)' if target == 'Revenue' else ''}"""

            latex = ""
            explanation = f"After all transactions:\n" + '\n'.join([f"  {k}: ${v:,}" for k, v in accounts.items()])
            hint = "Track how each transaction affects the relevant accounts."

            # Graph visualization showing account nodes and transaction edges
            plot_data = {
                'account_graph': accounts,
                'transactions': transactions,
                'title': "Account Balance Graph"
            }

        return Question(
            text=text,
            latex=latex,
            correct_answer=answer,
            explanation=explanation,
            category=self.CATEGORY,
            difficulty=difficulty,
            hint=hint,
            answer_type="numeric",
            plot_data=plot_data,
            requires_plot=plot_data is not None
        )


class AccountingQuestions:
    """Factory class for accounting question generators."""

    GENERATORS = [
        AccountingEquationQuestion,
        DoubleEntryQuestion,
        ProfitLossQuestion,
        BalanceSheetQuestion,
        GraphModelQuestion,
    ]

    @classmethod
    def get_random_question(cls, difficulty: DifficultyLevel) -> Question:
        valid_generators = [
            gen() for gen in cls.GENERATORS
            if gen().can_generate(difficulty)
        ]
        if not valid_generators:
            # Fallback
            if difficulty >= DifficultyLevel.HARD:
                return GraphModelQuestion().generate(DifficultyLevel.HARD)
            elif difficulty >= DifficultyLevel.MEDIUM:
                return DoubleEntryQuestion().generate(DifficultyLevel.MEDIUM)
            else:
                return AccountingEquationQuestion().generate(DifficultyLevel.EASY)

        generator = valid_generators[np.random.randint(0, len(valid_generators))]
        return generator.generate(difficulty)
