#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from .account_budget import *


def register():
    Pool.register(
        BudgetPosition,
        Budget,
        BudgetLine,
        BudgetAccounts,
        PrintBudgetStart,
        module='account_budget', type_='model')
    Pool.register(
        PrintBudget,
        module='account_budget', type_='wizard')
    Pool.register(
        BudgetReport,
        module='account_budget', type_='report')
