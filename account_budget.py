# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import datetime
from decimal import Decimal

from sql.aggregate import Sum
from sql.operators import Abs, In

from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.modules.jasper_reports.jasper import JasperReport

__all__ = ['BudgetAccounts', 'BudgetPosition', 'Budget', 'BudgetLine',
    'BudgetReport', 'PrintBudget', 'PrintBudgetStart']

_STATES = {
    'readonly': Eval('state') != 'draft',
    }
_DEPENDS = ['state']


class BudgetAccounts(ModelSQL):
    'AccountBudget - Accounts'
    __name__ = 'account_budget_post-account_account'
    _table = 'account_budget_rel'
    budget = fields.Many2One('account.budget.position',
        'Budgetary Postition', ondelete='CASCADE', select=True, required=True)
    account = fields.Many2One('account.account', 'Account',
        ondelete='CASCADE', select=True, required=True)


class BudgetPosition(ModelSQL, ModelView):
    'Budgetary Position'
    __name__ = 'account.budget.position'

    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete='RESTRICT')
    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    accounts = fields.Many2Many('account_budget_post-account_account',
        'budget', 'account', 'Accounts', domain=[('type', '!=', 'view')])
    lines = fields.One2Many('account.budget.line', 'general_budget',
        'Budget Lines', readonly=True)

    @classmethod
    def __setup__(cls):
        super(BudgetPosition, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company') or None


class Budget(Workflow, ModelSQL, ModelView):
    'Budget'
    __name__ = 'account.budget'

    state = fields.Selection([
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('validated', 'Validated'),
            ('done', 'Done'),
            ('cancel', 'Cancelled')],
        'Status', select=True, required=True, readonly=True)
    company = fields.Many2One('company.company', 'Company', required=True,
            ondelete='RESTRICT', states=_STATES, depends=_DEPENDS)
    name = fields.Char('Name', required=True, states=_STATES, depends=_DEPENDS)
    code = fields.Char('Code', required=True, states=_STATES, depends=_DEPENDS)
    validating_user = fields.Many2One('res.user', 'Validate User',
        readonly=True)
    start_date = fields.Date('Start Date', required=True, states=_STATES,
        depends=_DEPENDS)
    end_date = fields.Date('End Date', required=True, states=_STATES,
        depends=_DEPENDS)
    currency = fields.Many2One('currency.currency', 'Currency', required=True,
        states={
            'readonly': (Eval('state') != 'draft'),
            }, depends=['state'])
    lines = fields.One2Many('account.budget.line', 'budget',
        'Budget Lines', states=_STATES, depends=_DEPENDS)

    @classmethod
    def __setup__(cls):
        super(Budget, cls).__setup__()
        cls._transition_state = 'state'
        cls._transitions |= set((
                ('draft', 'confirmed'),
                ('confirmed', 'validated'),
                ('confirmed', 'cancel'),
                ('validated', 'done'),
                ('validated', 'cancel'),
                ('cancel', 'draft'),
                ))
        cls._buttons.update({
                'confirm': {
                    'invisible': Eval('state') != 'draft',
                    },
                'valid': {
                    'invisible': Eval('state') != 'confirmed',
                    },
                'done': {
                    'invisible': Eval('state') != 'validated',
                    },
                'draft': {
                    'invisible': Eval('state') != 'cancel',
                    },
                'cancel': {
                    'invisible': ~Eval('state').in_(['validated',
                            'confirmed']),
                    },
                })

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company') or None

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    def get_rec_name(self, name):
        return "%s - %s" % (self.code, self.name)

    @classmethod
    def search_rec_name(cls, name, clause):
        budgets = cls.search([('code',) + tuple(clause[1:])], order=[])
        if budgets:
            budgets += cls.search([('name',) + tuple(clause[1:])], order=[])

            return [('id', 'in', [budget.id for budget in budgets])]
        return [('name',) + tuple(clause[1:])]

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, budgets):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, budgets):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def valid(cls, budgets):
        cls.write(budgets, {
            'validating_user': Transaction().user,
        })

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, budgets):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, budgets):
        pass


class BudgetLine(ModelSQL, ModelView):
    'Budget Line'
    __name__ = 'account.budget.line'

    budget = fields.Many2One('account.budget', 'Budget',
        ondelete='CASCADE', select=True, required=True)
    general_budget = fields.Many2One('account.budget.position',
        'Budgetary Position', required=True)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    paid_date = fields.Date('Paid Date')
    planned_amount = fields.Numeric('Planned Amount', required=True,
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'])
    practical_amount = fields.Function(fields.Numeric('Practical Amount',
        depends=['currency_digits'], digits=(16, Eval('currency_digits', 2))),
        'get_practical_amount')
    theoritical_amount = fields.Function(fields.Numeric('Theoretical Amount',
        depends=['currency_digits'], digits=(16, Eval('currency_digits', 2))),
        'get_theoritical_amount')
    percentage = fields.Function(fields.Numeric('Percentage', digits=(16, 2)),
        'get_percentage')

    @classmethod
    def __setup__(cls):
        super(BudgetLine, cls).__setup__()
        cls._error_messages.update({
                'no_accounts': ('The General Budget "%s" has no accounts.'),
                })

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.budget and self.budget.currency:
            return self.budget.currency.digits
        return 2

    def get_practical_amount(self, name):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')

        transaction = Transaction()
        cursor = transaction.connection.cursor()
        context = transaction.context

        line = Line.__table__()
        move = Move.__table__()

        accounts = [x.id for x in self.general_budget.accounts]
        if not accounts:
            self.raise_user_error('no_accounts', self.general_budget.rec_name)
        end_date = context.get('end_date', self.end_date)
        start_date = context.get('start_date', self.start_date)
        cursor.execute(*line.join(move, condition=line.move == move.id).select(
                Sum(Abs(line.credit - line.debit)),
                where=((move.date >= start_date) & (move.date <= end_date) &
                    In(line.account, accounts))))
        result = cursor.fetchone()
        if result and result[0]:
            return result[0]
        return Decimal('0.0')

    def get_theoritical_amount(self, name):
        transaction = Transaction()
        context = transaction.context
        end_date = datetime.date.today()
        start_date = self.start_date
        end_date = context.get('end_date', self.end_date)
        start_date = context.get('start_date', datetime.date.today())

        if self.paid_date:
            if self.end_date <= self.paid_date:
                return Decimal('0.0')
            else:
                return self.planned_amount
        else:
            total = self.end_date - self.start_date
            elapsed = (min(self.end_date, end_date) -
                max(self.start_date, start_date))
            if end_date < self.start_date:
                elapsed = self.start_date - end_date

            if total.days:
                return ((Decimal(str(elapsed.days)) / Decimal(str(total.days)))
                    * self.planned_amount)
            else:
                return self.planned_amount

        return Decimal('0.0')

    def get_percentage(self, name):
        if self.theoritical_amount != Decimal('0.0'):
            return ((self.practical_amount or Decimal('0.0')) /
                self.theoritical_amount) * Decimal('100.0')
        return Decimal('0.0')


class BudgetReport(JasperReport):
    'Budget Report'
    __name__ = 'account.budget.report'

    @classmethod
    def execute(cls, ids, data):
        pool = Pool()
        transaction = Transaction()
        Budget = pool.get('account.budget')
        BudgetLine = pool.get('account.budget.line')

        budget = Budget(transaction.context['active_id'])

        parameters = {}
        parameters['start_date'] = str(data['start_date'])
        parameters['end_date'] = str(data['end_date'])
        parameters['budget'] = budget.rec_name
        parameters['currency'] = budget.currency.rec_name

        with transaction.set_context(start_date=data['start_date'],
                end_date=data['end_date']):
            ids = [x.id for x in BudgetLine.search(
                    [('budget', '=', budget.id)])]
            return super(BudgetReport, cls).execute(ids, {
                    'name': 'account_budget.budget',
                    'parameters': parameters,
                    'output_format': 'PDF',
                    })


class PrintBudgetStart(ModelView):
    'Print Budget Start'
    __name__ = 'account_budget.print_budget.start'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    @staticmethod
    def default_start_date():
        today = datetime.datetime.today()
        return datetime.datetime(today.year, 1, 1)

    @staticmethod
    def default_end_date():
        return datetime.datetime.today()


class PrintBudget(Wizard):
    'Print Budget'
    __name__ = 'account_budget.print_budget'
    start = StateView('account_budget.print_budget.start',
        'account_budget.print_budget_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account_budget.act_report_budget')

    def do_print_(self, action):
        data = {
            'start_date': self.start.start_date,
            'end_date': self.start.end_date,
            }
        return action, data

    def transition_print_(self):
        return 'end'
