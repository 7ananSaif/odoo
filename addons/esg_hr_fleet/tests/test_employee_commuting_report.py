from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import TransactionCase, freeze_time

from odoo.addons.mail.tests.common import mail_new_test_user


@freeze_time("2024-09-20")
class TestEmployeeCommutingReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env["res.company"].create({
            "name": "CommuteCo",
            "weekly_days_at_office": 5,
        })
        cls.bob = cls.env["hr.employee"].create({
            "name": "Bob Commuter",
            "company_id": cls.company.id,
        })
        cls.bob.distance_home_work = 10
        cls.driver_bob = cls.bob.work_contact_id

        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Audi"})
        model = cls.env["fleet.vehicle.model"].create({
            "brand_id": brand.id,
            "name": "A3",
        })
        cls.vehicle = cls.env["fleet.vehicle"].create({
            "name": "EcoCar",
            "model_id": model.id,
            "company_id": cls.company.id,
            "co2": 120,
        })

    def test_commuting_report_simple_case(self):
        self.env["fleet.vehicle.assignation.log"].create({
            "vehicle_id": self.vehicle.id,
            "driver_id": self.driver_bob.id,
            "date_start": date(2024, 6, 1),
            "date_end": date(2024, 6, 30),
        })

        report = self.env["esg.employee.commuting.report"].search([
            ("vehicle_id", "=", self.vehicle.id),
            ("driver_id", "=", self.driver_bob.id),
            ("date_from", "=", date(2024, 6, 1)),
        ])
        self.assertEqual(len(report), 1)

        commute_days = 30 * 5 / 7
        expected_km = 10 * 2 * commute_days
        expected_co2 = expected_km * 120 / 1e6

        self.assertAlmostEqual(report.total_distance, expected_km, places=2, msg="The total distance should match the expected computation.")
        self.assertAlmostEqual(report.total_co2, expected_co2, places=4, msg="The total emissions should match the expected computation.")

    def test_report_date_boundaries_across_months(self):
        self.env["fleet.vehicle.assignation.log"].create({
            "vehicle_id": self.vehicle.id,
            "driver_id": self.driver_bob.id,
            "date_start": date(2024, 6, 10),
            "date_end": date(2024, 7, 20),
        })
        reports = self.env["esg.employee.commuting.report"].search([
            ("vehicle_id", "=", self.vehicle.id),
            ("driver_id", "=", self.driver_bob.id),
        ])

        self.assertEqual(len(reports), 2, "The assignation log spans two months, and there should therefore be a report record for each month.")

    def test_zero_weekly_days_at_office(self):
        self.company.weekly_days_at_office = 0
        self.company.flush_recordset(["weekly_days_at_office"])

        self.env["fleet.vehicle.assignation.log"].create({
            "vehicle_id": self.vehicle.id,
            "driver_id": self.driver_bob.id,
            "date_start": date(2024, 6, 1),
            "date_end": date(2024, 6, 30),
        })

        report = self.env["esg.employee.commuting.report"].search([
            ("vehicle_id", "=", self.vehicle.id),
            ("driver_id", "=", self.driver_bob.id),
        ])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.total_distance, 0, "0 days per week at the office means no distance driven.")
        self.assertEqual(report.total_co2, 0, "No distance driven means no emissions.")

    @freeze_time(Date.today().strftime("%Y-%m-%d"))
    def test_open_ended_assignation(self):
        start_date = (Date.today() - relativedelta(months=3)).replace(day=1)

        log = self.env["fleet.vehicle.assignation.log"].create({
            "vehicle_id": self.vehicle.id,
            "driver_id": self.driver_bob.id,
            "date_start": start_date,
            "date_end": False,
        })
        log.flush_recordset()

        # Reinitialize the report to reflect the updated data
        self.env["esg.employee.commuting.report"].init()

        reports = self.env["esg.employee.commuting.report"].search([
            ("vehicle_id", "=", self.vehicle.id),
            ("driver_id", "=", self.driver_bob.id),
        ])

        self.assertEqual(len(reports), 4, "One record per month should be generated for the past 4 months.")

        expected_starts = {
            (start_date + relativedelta(months=i)).replace(day=1)
            for i in range(4)
        }
        actual_starts = {r.date_from for r in reports}
        self.assertEqual(expected_starts, actual_starts, "Each month in the range should be present in the report.")

    def test_no_distance_home_work(self):
        self.bob.version_id.distance_home_work = False
        self.bob.version_id.flush_recordset(["distance_home_work"])

        self.env["fleet.vehicle.assignation.log"].create({
            "vehicle_id": self.vehicle.id,
            "driver_id": self.driver_bob.id,
            "date_start": date(2024, 6, 1),
            "date_end": date(2024, 6, 30),
        })

        report = self.env["esg.employee.commuting.report"].search([
            ("vehicle_id", "=", self.vehicle.id),
        ])
        self.assertEqual(report.total_distance, 0, "No distance home-work should result in a distance of 0.")
        self.assertEqual(report.total_co2, 0, "No distance home-work should result in 0 emissions.")

    def test_vehicle_without_co2(self):
        self.vehicle.co2 = False
        self.vehicle.flush_recordset(["co2"])

        self.env["fleet.vehicle.assignation.log"].create({
            "vehicle_id": self.vehicle.id,
            "driver_id": self.driver_bob.id,
            "date_start": date(2024, 6, 1),
            "date_end": date(2024, 6, 30),
        })

        report = self.env["esg.employee.commuting.report"].search([
            ("vehicle_id", "=", self.vehicle.id),
        ])
        self.assertEqual(report.total_co2, 0, "A vehicle with no emissions set should generate a record, but with no emissions.")
        self.assertGreater(report.total_distance, 0, "The total distance, however, should be unaffected.")

    def test_log_with_driver_not_linked_to_employee(self):
        rogue_driver = self.env["res.partner"].create({"name": "Ghost Rider"})
        self.env["fleet.vehicle.assignation.log"].create({
            "vehicle_id": self.vehicle.id,
            "driver_id": rogue_driver.id,
            "date_start": date(2024, 6, 1),
            "date_end": date(2024, 6, 30),
        })
        report = self.env["esg.employee.commuting.report"].search([
            ("driver_id", "=", rogue_driver.id),
        ])
        self.assertFalse(report, "If the driver has no correspnding employee, no record should be generated.")

    def test_multiple_logs_and_drivers(self):
        alice = self.env["hr.employee"].create({
            "name": "Alice Rider",
            "company_id": self.company.id,
        })
        alice.distance_home_work = 20
        driver_alice = alice.work_contact_id

        brand2 = self.env["fleet.vehicle.model.brand"].create({"name": "Toyota"})
        model2 = self.env["fleet.vehicle.model"].create({
            "brand_id": brand2.id,
            "name": "Prius",
        })
        vehicle2 = self.env["fleet.vehicle"].create({
            "name": "HybridCar",
            "model_id": model2.id,
            "company_id": self.company.id,
            "co2": 80,
        })

        self.env["fleet.vehicle.assignation.log"].create([{
            "vehicle_id": self.vehicle.id,
            "driver_id": self.driver_bob.id,
            "date_start": date(2024, 6, 1),
            "date_end": date(2024, 6, 15),
        }, {
            "vehicle_id": self.vehicle.id,
            "driver_id": driver_alice.id,
            "date_start": date(2024, 6, 16),
            "date_end": date(2024, 6, 30),
        }, {
            "vehicle_id": vehicle2.id,
            "driver_id": driver_alice.id,
            "date_start": date(2024, 6, 1),
            "date_end": date(2024, 6, 30),
        }])
        self.env.flush_all()

        reports = self.env["esg.employee.commuting.report"].search([
            ("company_id", "=", self.company.id),
        ])
        self.assertEqual(len(reports), 3, "There should be 3 records in the report: 1 for each log, since they all are within the same month.")

        key_pairs = {(r.driver_id.id, r.vehicle_id.id) for r in reports}
        expected_pairs = {
            (self.driver_bob.id, self.vehicle.id),
            (driver_alice.id, self.vehicle.id),
            (driver_alice.id, vehicle2.id),
        }
        self.assertEqual(key_pairs, expected_pairs, "Each (driver, vehicle) pair should generate a distinct report record.")

    def test_report_multi_company(self):
        hr_user = mail_new_test_user(
            self.env,
            login="hr_commute_user",
            groups="fleet.fleet_group_user",
            company_id=self.company.id,
            company_ids=[self.company.id],
        )
        other_company = self.env["res.company"].create({
            "name": "OtherCo",
            "weekly_days_at_office": 5,
        })
        other_employee = self.env["hr.employee"].create({
            "name": "Other Bob",
            "company_id": other_company.id,
        })
        other_employee.distance_home_work = 50
        driver_other = other_employee.work_contact_id

        brand_other = self.env["fleet.vehicle.model.brand"].create({"name": "Renault"})
        model_other = self.env["fleet.vehicle.model"].create({
            "brand_id": brand_other.id,
            "name": "Clio",
        })
        vehicle_other = self.env["fleet.vehicle"].create({
            "name": "OtherCar",
            "model_id": model_other.id,
            "company_id": other_company.id,
            "co2": 100,
        })

        self.env["fleet.vehicle.assignation.log"].create([{
            "vehicle_id": vehicle_other.id,
            "driver_id": driver_other.id,
            "date_start": date(2024, 6, 1),
            "date_end": date(2024, 6, 30),
        }, {
            "vehicle_id": self.vehicle.id,
            "driver_id": self.driver_bob.id,
            "date_start": date(2024, 6, 1),
            "date_end": date(2024, 6, 30),
        }])
        self.env.flush_all()

        reports = self.env["esg.employee.commuting.report"].with_user(hr_user).with_context(
            allowed_company_ids=[self.company.id],
        ).search([])
        self.assertEqual(len(reports), 1, "Only report records from the current company should be returned.")
        self.assertEqual(reports.company_id, self.company, "The report record should belong to the current company.")
