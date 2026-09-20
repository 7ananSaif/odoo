# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase
from datetime import date


class TestHrContractSalaryOffer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.offer_calendar = cls.env['resource.calendar'].create({
            'name': 'Offer Calendar',
            'hours_per_week': 40,
        })
        cls.version_calendar = cls.env['resource.calendar'].create({
            'name': 'Version Calendar',
            'hours_per_day': 7.6,
            'hours_per_week': 38,  # if the version uses this calendar, version.work_time_rate will be 0.95 cause relative to company weekly working hours
            'full_time_required_hours': 38,
        })

        cls.struct_type = cls.env['hr.payroll.structure.type'].create({'name': 'Regular'})
        cls.structure = cls.env['hr.payroll.structure'].create({
            'name': 'Regular structure',
            'type_id': cls.struct_type.id,
        })
        cls.struct_type.default_struct_id = cls.structure

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Tom Ato',
            'wage': 2000,
            'structure_type_id': cls.struct_type.id,
            'contract_date_start': date.today()
        })
        cls.version = cls.employee.version_ids[0]

    def test_version_calendar_priority(self):
        offer = self.env['hr.contract.salary.offer'].create({
            'employee_id': self.employee.id,
            'structure_id': self.structure.id,
            'monthly_wage': 2000,
            'resource_calendar_id': self.offer_calendar.id,
        })

        # case 1: version calendar empty -> offer calendar is used
        self.version.resource_calendar_id = False
        offer._compute_salary()
        version = offer._get_version()
        self.assertEqual(version.resource_calendar_id, self.offer_calendar)
        self.assertAlmostEqual(offer.gross_wage, 2000.0, places=2)  # check gross salary computed in Salary Simulation Preview

        # case 2: version calendar set -> version calendar is kept
        self.version.resource_calendar_id = self.version_calendar
        offer._compute_salary()
        version = offer._get_version()
        self.assertEqual(version.resource_calendar_id, self.version_calendar)
        self.assertAlmostEqual(offer.gross_wage, 1900.0, places=2)
        self.assertAlmostEqual(version.work_time_rate, 0.95, 2)
