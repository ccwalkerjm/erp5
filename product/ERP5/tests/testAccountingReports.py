#############################################################################
#
# Copyright (c) 2006 Nexedi SA and Contributors. All Rights Reserved.
#          Jerome Perrin <jerome@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################

"""Tests Standards ERP5 Accounting Reports
"""

import unittest

from DateTime import DateTime

from Products.ERP5.tests.testAccounting import AccountingTestCase
from Products.ERP5Form.Selection import Selection


class TestAccountingReports(AccountingTestCase):
  """Test Accounting reports
  
  Test basic cases of gathering data to render reports, the purpose of those
  tests is to exercise basic reporting features to make sure no regression
  happen. Input data used for tests usually contain edge cases, for example:
    * movements at the boundaries of the period.
    * movements with other simulation states.
    * movements with node in the section_category we want to exclude (Persons).
    * movements with source & destination for other sections.
    ...
  """

  # utility methods for ERP5 Report
  def getReportSectionList(self, report_name):
    """Get the list of report sections in a report."""
    report = getattr(self.portal, report_name)
    report_method = getattr(self.portal, report.report_method)
    return report_method()

  def getListBoxLineList(self, report_section):
    """Render the listbox in a report section, return None if no listbox exists
    in the report_section.
    """
    result = None
    here = report_section.getObject(self.portal)
    report_section.pushReport(self.portal)
    form = getattr(here, report_section.getFormId())
    if form.has_field('listbox'):
      result = form.listbox.get_value('default',
                                      render_format='list',
                                      REQUEST=self.portal.REQUEST)
    report_section.popReport(self.portal)
    return result

  def checkLineProperties(self, line, **kw):
    """Check properties of a report line.
    """
    for k, v in kw.items():
      self.assertEquals(v, line.getColumnProperty(k),
          '`%s`: expected: %r actual: %r' % (k, v, line.getColumnProperty(k)))
    
  def testJournal(self):
    # Journal report.
    # this will be a journal for 2006/02/02, for Sale Invoice Transaction
    # portal type. Many cases are covered by this test.
    
    account_module = self.account_module
    # before the date
    self._makeOne(
              portal_type='Accounting Transaction',
              simulation_state='delivered',
              start_date=DateTime(2006, 1, 1),
              lines=(dict(source_value=account_module.equity,
                          source_debit=100),
                     dict(source_value=account_module.stocks,
                          source_credit=100)))

    # during the period
    first = self._makeOne(
              portal_type='Sale Invoice Transaction',
              title='First One',
              simulation_state='delivered',
              destination_section_value=self.organisation_module.client_1,
              start_date=DateTime(2006, 2, 2),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=119.60),
                     dict(source_value=account_module.collected_vat,
                          source_credit=19.60),
                     dict(source_value=account_module.goods_sales,
                          source_credit=100.00)))

    second = self._makeOne(
              portal_type='Sale Invoice Transaction',
              title='Second One',
              simulation_state='delivered',
              destination_section_value=self.organisation_module.client_2,
              start_date=DateTime(2006, 2, 2),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=239.20),
                     dict(source_value=account_module.collected_vat,
                          source_credit=39.20),
                     dict(source_value=account_module.goods_sales,
                          source_credit=200.00)))

    third = self._makeOne(
              title='Third One',
              portal_type='Sale Invoice Transaction',
              simulation_state='delivered',
              # with a person member of the group
              destination_section_value=self.person_module.john_smith,
              start_date=DateTime(2006, 2, 2, 2, 2), # with hour:minutes
              lines=(dict(source_value=account_module.receivable,
                          destination_value=account_module.receivable,
                          source_debit=358.80),
                     dict(source_value=account_module.collected_vat,
                          source_credit=58.80),
                     dict(source_value=account_module.goods_sales,
                          # with a title on the line
                          title='Line Title',
                          source_credit=300.00)))

    # another portal type
    self._makeOne(
              portal_type='Accounting Transaction',
              simulation_state='delivered',
              start_date=DateTime(2006, 2, 2),
              lines=(dict(source_value=account_module.equity,
                          source_debit=111),
                     dict(source_value=account_module.stocks,
                          source_credit=111)))

    # after the period
    self._makeOne(
              portal_type='Sale Invoice Transaction',
              simulation_state='delivered',
              destination_section_value=self.organisation_module.client_2,
              start_date=DateTime(2006, 2, 3),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=598.00),
                     dict(source_value=account_module.collected_vat,
                          source_credit=98.00),
                     dict(source_value=account_module.goods_sales,
                          source_credit=500.00)))

    # set request variables and render                 
    request_form = self.portal.REQUEST.form
    request_form['at_date'] = DateTime(2006, 2, 2)
    request_form['section_category'] = 'group/demo_group'
    request_form['portal_type'] = ['Sale Invoice Transaction']
    request_form['simulation_state'] = ['delivered']
    
    report_section_list = self.getReportSectionList(
                               'AccountingTransactionModule_viewJournalReport')
    self.assertEquals(1, len(report_section_list))
    
    # precision is set in the REQUEST (so that fields know how to format)
    precision = self.portal.REQUEST.get('precision')
    self.assertEquals(2, precision)
    
    line_list = self.getListBoxLineList(report_section_list[0])
    data_line_list = [l for l in line_list if l.isDataLine()]
    # we have 3 transactions, with 3 lines each
    self.assertEquals(9, len(data_line_list))
    
    # test columns values
    line = data_line_list[0]
    self.assertEquals(line.column_id_list,
        ['specific_reference', 'date', 'title', 'node_title',
         'mirror_section_title', 'debit', 'credit'])
    
    # First Transaction
    line = data_line_list[0]
    self.assertEquals(first.getSourceReference(),
                      line.getColumnProperty('specific_reference'))
    self.assertEquals(DateTime(2006, 2, 2),
                      line.getColumnProperty('date'))
    self.assertEquals('First One', line.getColumnProperty('title'))
    self.assertEquals('41', line.getColumnProperty('node_title'))
    self.assertEquals('Client 1',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(119.60, line.getColumnProperty('debit'))
    self.assertEquals(0, line.getColumnProperty('credit'))
    line = data_line_list[1]
    # some values are only present when we display the first line of the
    # transaction (this is a way to see different transactions)
    self.failIf(line.getColumnProperty('specific_reference'))
    self.failIf(line.getColumnProperty('date'))
    self.failIf(line.getColumnProperty('title'))
    self.assertEquals('4457', line.getColumnProperty('node_title'))
    self.assertEquals('Client 1',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(0, line.getColumnProperty('debit'))
    self.assertEquals(19.60, line.getColumnProperty('credit'))
    line = data_line_list[2]
    self.failIf(line.getColumnProperty('specific_reference'))
    self.failIf(line.getColumnProperty('date'))
    self.failIf(line.getColumnProperty('title'))
    self.assertEquals('7', line.getColumnProperty('node_title'))
    self.assertEquals('Client 1',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(0, line.getColumnProperty('debit'))
    self.assertEquals(100.00, line.getColumnProperty('credit'))

    # Second Transaction
    line = data_line_list[3]
    self.assertEquals(second.getSourceReference(),
                      line.getColumnProperty('specific_reference'))
    self.assertEquals(DateTime(2006, 2, 2), line.getColumnProperty('date'))
    self.assertEquals('Second One', line.getColumnProperty('title'))
    self.assertEquals('41', line.getColumnProperty('node_title'))
    self.assertEquals('Client 2',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(239.20, line.getColumnProperty('debit'))
    self.assertEquals(0, line.getColumnProperty('credit'))
    line = data_line_list[4]
    self.failIf(line.getColumnProperty('specific_reference'))
    self.failIf(line.getColumnProperty('date'))
    self.failIf(line.getColumnProperty('title'))
    self.assertEquals('4457', line.getColumnProperty('node_title'))
    self.assertEquals('Client 2',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(0, line.getColumnProperty('debit'))
    self.assertEquals(39.20, line.getColumnProperty('credit'))
    line = data_line_list[5]
    self.failIf(line.getColumnProperty('specific_reference'))
    self.failIf(line.getColumnProperty('date'))
    self.failIf(line.getColumnProperty('title'))
    self.assertEquals('7', line.getColumnProperty('node_title'))
    self.assertEquals('Client 2',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(0, line.getColumnProperty('debit'))
    self.assertEquals(200, line.getColumnProperty('credit'))

    # Third Transaction
    line = data_line_list[6]
    self.assertEquals(third.getSourceReference(),
                      line.getColumnProperty('specific_reference'))
    self.assertEquals(DateTime(2006, 2, 2, 2, 2), # 2006/02/02 will be
                              # displayed, but this rendering level cannot be
                              # tested with this framework
                      line.getColumnProperty('date'))
    self.assertEquals('Third One', line.getColumnProperty('title'))
    self.assertEquals('41', line.getColumnProperty('node_title'))
    self.assertEquals('John Smith',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(358.80, line.getColumnProperty('debit'))
    self.assertEquals(0, line.getColumnProperty('credit'))
    line = data_line_list[7]
    self.failIf(line.getColumnProperty('specific_reference'))
    self.failIf(line.getColumnProperty('date'))
    self.failIf(line.getColumnProperty('title'))
    self.assertEquals('4457', line.getColumnProperty('node_title'))
    self.assertEquals('John Smith',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(0, line.getColumnProperty('debit'))
    self.assertEquals(58.80, line.getColumnProperty('credit'))
    line = data_line_list[8]
    self.failIf(line.getColumnProperty('specific_reference'))
    self.failIf(line.getColumnProperty('date'))
    # If a title is set on the line, we can see it on this report
    self.assertEquals('Line Title', line.getColumnProperty('title'))
    self.assertEquals('7', line.getColumnProperty('node_title'))
    self.assertEquals('John Smith',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(0, line.getColumnProperty('debit'))
    self.assertEquals(300.0, line.getColumnProperty('credit'))

    # Stat Line
    stat_line = line_list[-1]
    self.failUnless(stat_line.isStatLine())
    self.failIf(stat_line.getColumnProperty('specific_reference'))
    self.failIf(stat_line.getColumnProperty('date'))
    self.failIf(stat_line.getColumnProperty('title'))
    self.failIf(stat_line.getColumnProperty('node_title'))
    self.failIf(stat_line.getColumnProperty('mirror_section_title'))
    # when printing the report, the field does the rounding, so we can round in
    # the test
    self.assertEquals(717.60, round(stat_line.getColumnProperty('debit'),
                                    precision))
    self.assertEquals(717.60, round(stat_line.getColumnProperty('credit'),
                                    precision))


  def testJournalWithBankAccount(self):
    # Journal report when selecting a bank account
    # this will be a journal for 2006/02/02, whith two bank accounts
    
    account_module = self.account_module

    bank1 = self.section.newContent(portal_type='Bank Account')
    bank1.validate()
    bank2 = self.section.newContent(portal_type='Bank Account')
    bank2.validate()

    transaction = self._makeOne(
              portal_type='Payment Transaction',
              title='Good One',
              simulation_state='delivered',
              source_payment_value=bank1,
              destination_section_value=self.organisation_module.client_1,
              start_date=DateTime(2006, 2, 2),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=100.0),
                     dict(source_value=account_module.bank,
                          source_credit=100.0)))
    
    self._makeOne(
              portal_type='Payment Transaction',
              title='Other One',
              simulation_state='delivered',
              source_payment_value=bank2,
              destination_section_value=self.organisation_module.client_1,
              start_date=DateTime(2006, 2, 2),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=200.0),
                     dict(source_value=account_module.bank,
                          source_credit=200.0)))
    
    
    # set request variables and render                 
    request_form = self.portal.REQUEST.form
    request_form['at_date'] = DateTime(2006, 2, 2)
    request_form['section_category'] = 'group/demo_group'
    request_form['portal_type'] = ['Payment Transaction']
    request_form['simulation_state'] = ['delivered']
    request_form['payment'] = bank1.getRelativeUrl()
    
    report_section_list = self.getReportSectionList(
                               'AccountingTransactionModule_viewJournalReport')
    self.assertEquals(1, len(report_section_list))
    
    line_list = self.getListBoxLineList(report_section_list[0])
    data_line_list = [l for l in line_list if l.isDataLine()]
    # we have 1 transactions with 2 lines
    self.assertEquals(2, len(data_line_list))
    
    line = data_line_list[0]
    self.assertEquals(transaction.getSourceReference(),
                      line.getColumnProperty('specific_reference'))
    self.assertEquals(DateTime(2006, 2, 2),
                      line.getColumnProperty('date'))
    self.assertEquals('Good One', line.getColumnProperty('title'))
    self.assertEquals('41', line.getColumnProperty('node_title'))
    self.assertEquals('Client 1',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(100.00, line.getColumnProperty('debit'))
    self.assertEquals(0, line.getColumnProperty('credit'))
    line = data_line_list[1]
    # some values are only present when we display the first line of the
    # transaction (this is a way to see different transactions)
    self.failIf(line.getColumnProperty('specific_reference'))
    self.failIf(line.getColumnProperty('date'))
    self.failIf(line.getColumnProperty('title'))
    self.assertEquals('5', line.getColumnProperty('node_title'))
    self.assertEquals('Client 1',
                      line.getColumnProperty('mirror_section_title'))
    self.assertEquals(0, line.getColumnProperty('debit'))
    self.assertEquals(100.00, line.getColumnProperty('credit'))
    
    # Stat Line
    stat_line = line_list[-1]
    self.failUnless(stat_line.isStatLine())
    self.assertEquals(100, stat_line.getColumnProperty('debit'))
    self.assertEquals(100, stat_line.getColumnProperty('credit'))


  def createAccountStatementDataSet(self):
    """Create transactions for Account statement report.
    """
    account_module = self.account_module

    bank1 = self.section.newContent(portal_type='Bank Account')
    bank1.validate()
    
    # before
    t1 = self._makeOne(
              portal_type='Accounting Transaction',
              title='Transaction 1',
              source_reference='1',
              simulation_state='delivered',
              destination_section_value=self.organisation_module.client_1,
              start_date=DateTime(2006, 2, 1),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=100.0),
                     dict(source_value=account_module.payable,
                          source_credit=100.0)))
    
    t2 = self._makeOne(
              portal_type='Accounting Transaction',
              title='Transaction 2',
              source_reference='2',
              simulation_state='delivered',
              destination_section_value=self.organisation_module.client_1,
              start_date=DateTime(2006, 2, 1, 0, 1),
              lines=(dict(source_value=account_module.payable,
                          source_debit=200.0),
                     dict(source_value=account_module.receivable,
                          source_credit=200.0)))
    
    # in the period
    t3 = self._makeOne(
              portal_type='Payment Transaction',
              title='Transaction 3',
              source_reference='3',
              simulation_state='delivered',
              source_payment_value=bank1,
              destination_section_value=self.organisation_module.client_1,
              start_date=DateTime(2006, 2, 2, 0, 2),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=300.0),
                     dict(source_value=account_module.bank,
                          source_credit=300.0)))
    
    t4 = self._makeOne(
              portal_type='Payment Transaction',
              title='Transaction 4',
              destination_reference='4',
              simulation_state='delivered',
              destination_section_value=self.section,
              destination_payment_value=bank1,
              source_section_value=self.organisation_module.client_2,
              stop_date=DateTime(2006, 2, 2, 0, 3),
              start_date=DateTime(2006, 2, 1),
              lines=(dict(destination_value=account_module.receivable,
                          destination_debit=400.0),
                     dict(destination_value=account_module.bank,
                          destination_credit=400.0)))
    
    t5 = self._makeOne(
              portal_type='Accounting Transaction',
              title='Transaction 5',
              source_reference='5',
              simulation_state='delivered',
              destination_section_value=self.person_module.john_smith,
              start_date=DateTime(2006, 2, 2, 0, 4),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=500.0),
                     dict(source_value=account_module.bank,
                          source_credit=500.0)))
    
    t6 = self._makeOne(
              portal_type='Purchase Invoice Transaction',
              title='Transaction 6',
              destination_reference='6',
              simulation_state='delivered',
              source_section_value=self.organisation_module.client_1,
              stop_date=DateTime(2006, 2, 2, 0, 5),
              lines=(dict(destination_value=account_module.receivable,
                          destination_debit=600.0),
                     dict(destination_value=account_module.bank,
                          destination_credit=600.0)))
    
    # another simulation state                 
    t7 = self._makeOne(
              portal_type='Accounting Transaction',
              title='Transaction 7',
              source_reference='7',
              simulation_state='stopped',
              destination_section_value=self.organisation_module.client_1,
              start_date=DateTime(2006, 2, 2, 0, 6),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=700.0),
                     dict(source_value=account_module.bank,
                          source_credit=700.0)))
    
    # after the period
    t8 = self._makeOne(
              portal_type='Accounting Transaction',
              title='Transaction 8',
              source_reference='8',
              simulation_state='delivered',
              destination_section_value=self.organisation_module.client_1,
              start_date=DateTime(2006, 2, 3),
              lines=(dict(source_value=account_module.receivable,
                          source_debit=800.0),
                     dict(source_value=account_module.bank,
                          source_credit=800.0)))
    
    return bank1, (t1, t2, t3, t4, t5, t6, t7, t8)


  def testAccountStatement(self):
    # Simple Account Statement for "Receivable" account
    self.createAccountStatementDataSet()
    
    # set request variables and render                 
    request_form = self.portal.REQUEST.form
    request_form['node'] = \
                self.portal.account_module.receivable.getRelativeUrl()
    request_form['at_date'] = DateTime(2006, 2, 2)
    request_form['section_category'] = 'group/demo_group'
    request_form['simulation_state'] = ['delivered']
    
    report_section_list = self.getReportSectionList(
                               'AccountModule_viewAccountStatementReport')
    self.assertEquals(1, len(report_section_list))
    
    # precision is set in the REQUEST (so that fields know how to format)
    precision = self.portal.REQUEST.get('precision')
    self.assertEquals(2, precision)
    
    line_list = self.getListBoxLineList(report_section_list[0])
    data_line_list = [l for l in line_list if l.isDataLine()]
    # we have 6 transactions, because 7th is after
    self.assertEquals(6, len(data_line_list))
    
    # test columns values
    line = data_line_list[0]
    self.assertEquals(line.column_id_list,
        ['Movement_getSpecificReference', 'date',
         'Movement_getExplanationTitle', 'Movement_getMirrorSectionTitle',
         'debit', 'credit', 'running_total_price'])
    
    self.checkLineProperties(data_line_list[0],
                             Movement_getSpecificReference='1',
                             date=DateTime(2006, 2, 1),
                             Movement_getExplanationTitle='Transaction 1',
                             Movement_getMirrorSectionTitle='Client 1',
                             debit=100,
                             credit=0,
                             running_total_price=100)
    
    self.checkLineProperties(data_line_list[1],
                             Movement_getSpecificReference='2',
                             date=DateTime(2006, 2, 1, 0, 1),
                             Movement_getExplanationTitle='Transaction 2',
                             Movement_getMirrorSectionTitle='Client 1',
                             debit=0,
                             credit=200,
                             running_total_price=-100)
    
    self.checkLineProperties(data_line_list[2],
                             Movement_getSpecificReference='3',
                             date=DateTime(2006, 2, 2, 0, 2),
                             Movement_getExplanationTitle='Transaction 3',
                             Movement_getMirrorSectionTitle='Client 1',
                             debit=300,
                             credit=0,
                             running_total_price=200)

    self.checkLineProperties(data_line_list[3],
                             Movement_getSpecificReference='4',
                             date=DateTime(2006, 2, 2, 0, 3),
                             Movement_getExplanationTitle='Transaction 4',
                             Movement_getMirrorSectionTitle='Client 2',
                             debit=400,
                             credit=0,
                             running_total_price=600)

    self.checkLineProperties(data_line_list[4],
                             Movement_getSpecificReference='5',
                             date=DateTime(2006, 2, 2, 0, 4),
                             Movement_getExplanationTitle='Transaction 5',
                             Movement_getMirrorSectionTitle='John Smith',
                             debit=500,
                             credit=0,
                             running_total_price=1100)

    self.checkLineProperties(data_line_list[5],
                             Movement_getSpecificReference='6',
                             date=DateTime(2006, 2, 2, 0, 5),
                             Movement_getExplanationTitle='Transaction 6',
                             Movement_getMirrorSectionTitle='Client 1',
                             debit=600,
                             credit=0,
                             running_total_price=1700)

    self.failUnless(line_list[-1].isStatLine())
    self.checkLineProperties(line_list[-1],
                             Movement_getSpecificReference=None,
                             date=None,
                             Movement_getExplanationTitle=None,
                             Movement_getMirrorSectionTitle=None,
                             debit=1900,
                             credit=200,
                             running_total_price=None)


  def testAccountStatementFromDateSummary(self):
    # A from date summary shows balance at the beginning of the period
    self.createAccountStatementDataSet()
    
    # set request variables and render                 
    request_form = self.portal.REQUEST.form
    request_form['node'] = \
                self.portal.account_module.receivable.getRelativeUrl()
    request_form['from_date'] = DateTime(2006, 2, 2)
    request_form['at_date'] = DateTime(2006, 2, 2)
    request_form['section_category'] = 'group/demo_group'
    request_form['simulation_state'] = ['delivered']
    
    report_section_list = self.getReportSectionList(
                               'AccountModule_viewAccountStatementReport')
    self.assertEquals(1, len(report_section_list))
    line_list = self.getListBoxLineList(report_section_list[0])
    data_line_list = [l for l in line_list if l.isDataLine()]
    # we have 1 summary line and 4 transactions
    self.assertEquals(5, len(data_line_list))
 
    self.checkLineProperties(data_line_list[0],
                             Movement_getSpecificReference='Previous Balance',
                             date=DateTime(2006, 2, 2),
                             Movement_getExplanationTitle='',
                             Movement_getMirrorSectionTitle='',
                             debit=100,
                             credit=200,
                             running_total_price=-100)
    
    self.checkLineProperties(data_line_list[1],
                             Movement_getSpecificReference='3',
                             date=DateTime(2006, 2, 2, 0, 2),
                             Movement_getExplanationTitle='Transaction 3',
                             Movement_getMirrorSectionTitle='Client 1',
                             debit=300,
                             credit=0,
                             running_total_price=200)

    self.checkLineProperties(data_line_list[2],
                             Movement_getSpecificReference='4',
                             date=DateTime(2006, 2, 2, 0, 3),
                             Movement_getExplanationTitle='Transaction 4',
                             Movement_getMirrorSectionTitle='Client 2',
                             debit=400,
                             credit=0,
                             running_total_price=600)

    self.checkLineProperties(data_line_list[3],
                             Movement_getSpecificReference='5',
                             date=DateTime(2006, 2, 2, 0, 4),
                             Movement_getExplanationTitle='Transaction 5',
                             Movement_getMirrorSectionTitle='John Smith',
                             debit=500,
                             credit=0,
                             running_total_price=1100)

    self.checkLineProperties(data_line_list[4],
                             Movement_getSpecificReference='6',
                             date=DateTime(2006, 2, 2, 0, 5),
                             Movement_getExplanationTitle='Transaction 6',
                             Movement_getMirrorSectionTitle='Client 1',
                             debit=600,
                             credit=0,
                             running_total_price=1700)

    self.failUnless(line_list[-1].isStatLine())
    self.checkLineProperties(line_list[-1], debit=1900, credit=200,)


  def testAccountStatementFromDateSummaryEmpty(self):
    # A from date summary shows balance at the beginning of the period, but
    # avoids showing a '0' line
    self.createAccountStatementDataSet()
    
    # set request variables and render                 
    request_form = self.portal.REQUEST.form
    request_form['node'] = \
                self.portal.account_module.receivable.getRelativeUrl()
    request_form['from_date'] = DateTime(2000, 2, 2)
    request_form['at_date'] = DateTime(2006, 2, 2)
    request_form['section_category'] = 'group/demo_group'
    request_form['simulation_state'] = ['delivered']
    
    report_section_list = self.getReportSectionList(
                               'AccountModule_viewAccountStatementReport')
    self.assertEquals(1, len(report_section_list))
    line_list = self.getListBoxLineList(report_section_list[0])
    data_line_list = [l for l in line_list if l.isDataLine()]
    self.assertNotEquals('Previous Balance',
          data_line_list[0].getColumnProperty('Movement_getSpecificReference'))

    
  def testAccountStatementMirrorSection(self):
    # 'Mirror Section' parameter is taken into account.
    self.createAccountStatementDataSet()
    
    # set request variables and render                 
    request_form = self.portal.REQUEST.form
    request_form['node'] = \
                self.portal.account_module.receivable.getRelativeUrl()
    request_form['mirror_section'] = \
                self.portal.organisation_module.client_2.getRelativeUrl()
    request_form['from_date'] = DateTime(2006, 2, 2)
    request_form['at_date'] = DateTime(2006, 2, 2)
    request_form['section_category'] = 'group/demo_group'
    request_form['simulation_state'] = ['delivered']
    
    report_section_list = self.getReportSectionList(
                                    'AccountModule_viewAccountStatementReport')
    self.assertEquals(1, len(report_section_list))
    line_list = self.getListBoxLineList(report_section_list[0])
    data_line_list = [l for l in line_list if l.isDataLine()]
    self.assertEquals(1, len(data_line_list))

    self.checkLineProperties(data_line_list[0],
                             Movement_getSpecificReference='4',
                             date=DateTime(2006, 2, 2, 0, 3),
                             Movement_getExplanationTitle='Transaction 4',
                             Movement_getMirrorSectionTitle='Client 2',
                             debit=400,
                             credit=0,
                             running_total_price=400)
    
    self.failUnless(line_list[-1].isStatLine())
    self.checkLineProperties(line_list[-1], debit=400, credit=0)


  def testAccountStatementSimulationState(self):
    # Simulation State parameter is taken into account.
    self.createAccountStatementDataSet()
    
    # set request variables and render                 
    request_form = self.portal.REQUEST.form
    request_form['node'] = \
                  self.portal.account_module.receivable.getRelativeUrl()
    request_form['at_date'] = DateTime(2006, 2, 2)
    request_form['section_category'] = 'group/demo_group'
    request_form['simulation_state'] = ['stopped', 'confirmed']

    report_section_list = self.getReportSectionList(
                                    'AccountModule_viewAccountStatementReport')
    self.assertEquals(1, len(report_section_list))
    line_list = self.getListBoxLineList(report_section_list[0])
    data_line_list = [l for l in line_list if l.isDataLine()]
    self.assertEquals(1, len(data_line_list))
    
    self.checkLineProperties(data_line_list[0],
                             Movement_getSpecificReference='7',
                             date=DateTime(2006, 2, 2, 0, 6),
                             Movement_getExplanationTitle='Transaction 7',
                             Movement_getMirrorSectionTitle='Client 1',
                             debit=700,
                             credit=0,
                             running_total_price=700)
    
    self.failUnless(line_list[-1].isStatLine())
    self.checkLineProperties(line_list[-1], debit=700, credit=0)


def test_suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(TestAccountingReports))
  return suite

