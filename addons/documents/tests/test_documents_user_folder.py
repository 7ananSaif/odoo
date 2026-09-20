from odoo import Command
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tests import users

from odoo.addons.documents.controllers.documents import ShareRoute
from odoo.addons.documents.tests.test_documents_common import TransactionCaseDocuments


class TestDocumentsUserFolder(TransactionCaseDocuments):

    def assertDocumentsEqual(self, actual, expected):
        missing = (expected - actual).mapped("name")
        extra = (actual - expected).mapped("name")
        msg = f"{f'Missing: {missing}, ' if missing else ''}{f'Unexpected: {extra}' if extra else ''}"
        self.assertEqual(actual, expected, msg=msg)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_sys_admin = cls.env['res.users'].create([
            {
                'group_ids': [Command.link(cls.env.ref('documents.group_documents_system').id)],
                'login': "doc_system",
                'name': "Documents System Administrator",
            },
        ])
        (
            cls.company_doc,
            cls.company_restr_doc,
            cls.internal_drive,
            cls.company_folder,
            cls.company_restr_folder,
        ) = cls.env['documents.document'].sudo().create([
            {'name': 'Company Document', 'owner_id': False, 'access_internal': 'view'},
            {'name': 'Company Document Restricted', 'owner_id': False},
            {
                'name': "Internal User's Drive Document",
                'owner_id': cls.internal_user.id,
                'type': 'folder',
            },
            {
                'name': 'Company Folder',
                'type': 'folder',
                'access_internal': 'edit',
                'owner_id': False,
            },
            {
                'name': 'Company Restricted Folder',
                'type': 'folder',
                'access_internal': 'none',
                'owner_id': False,
                'access_ids': False,
            },
        ])

        cls.sub_company_admin, cls.sub_drive_admin = cls.env['documents.document'].sudo().create([{
            'name': f'{label} Admin Subfolder',
            'type': 'folder',
            'folder_id': folder.id,
            'owner_id': False,
            'access_internal': 'none',
            'access_ids': False,
        } for label, folder in (('Company', cls.company_folder), ('Drive', cls.internal_drive))])
        (
            cls.shared_doc_company_sub,
            cls.shared_doc_drive,
            cls.shared_doc_company
        ) = cls.env["documents.document"].create([{
            'name': f'{label} Shared doc',
            'folder_id': folder.id,
            'access_internal': 'view',
        } for (label, folder) in (
            ('Company', cls.sub_company_admin),
            ('Drive', cls.sub_drive_admin),
            ('Company Restricted', cls.company_restr_folder))
        ])
        cls.test_documents = (
            cls.company_doc  # no owner, access_internal='view'
            | cls.company_restr_doc  # no owner, but no access to internal users
            | cls.internal_drive  # internal_user's drive
            | cls.folder_a  # doc_user's drive
            | cls.folder_a_a
            | cls.folder_b  # doc_user's drive
            | cls.company_folder
            | cls.sub_company_admin  # Company subfolder, restricted
            | cls.shared_doc_company_sub
            | cls.sub_drive_admin  # internal_user's drive subfolder, restricted
            | cls.shared_doc_drive
            | cls.company_restr_folder
            | cls.shared_doc_company  # Company folder, restricted
        )
        cls.folder_a.action_update_access_rights(
            access_internal='edit',
            partners={cls.portal_user.partner_id: ('view', False)}
        )
        # Log access to folder_a
        for user in cls.doc_user, cls.document_sys_admin, cls.portal_user, cls.internal_user:
            ShareRoute._upsert_last_access_date(cls.env(user=user), cls.folder_a)

        cls.company_restr_doc.action_update_access_rights(partners={cls.doc_user.partner_id: ('view', False)})
        cls.env['documents.document'].search([('id', 'not in', cls.test_documents.ids)]).action_archive()

    @users('dtdm')
    def test_create_with_default_user_folder_id(self):
        context = {'default_user_folder_id': 'COMPANY'}
        no_folder = self.env['documents.document']
        no_user = self.env['res.users']
        cases = [
            (
                {'name': 'Company root, no vals'},
                {'folder_id': no_folder, 'owner_id': no_user}
            ), (
                {'name': 'In folder A > A from folder_id in vals', 'folder_id': self.folder_a_a.id},
                {'folder_id': self.folder_a_a, 'owner_id': self.document_manager, 'user_folder_id': str(self.folder_a_a.id)}
            ), (
                {'name': 'In folder A from user_folder_id in vals', 'user_folder_id': str(self.folder_a.id)},
                {'folder_id': self.folder_a, 'owner_id': self.document_manager, 'user_folder_id': str(self.folder_a.id)}
            ), (
                {'name': 'In My Drive from user_folder_id in vals', 'user_folder_id': 'MY'},
                {'folder_id': no_folder, 'owner_id': self.document_manager, 'user_folder_id': 'MY'}
            ), (
                {'name': 'In My Drive from owner_id in vals', 'owner_id': self.document_manager.id},
                {'folder_id': no_folder, 'owner_id': self.document_manager, 'user_folder_id': 'MY'}
            )
        ]
        for vals, expected in cases:
            with self.subTest(vals=vals):
                doc = self.env['documents.document'].with_context(context).create(vals)
                for key, value in expected.items():
                    self.assertEqual(doc[key], value)

    @users('internal_user')
    def test_create_write_user_folder_id(self):
        defaults, company, my, folder_a_b, folder_a_b_2 = self.env['documents.document'].with_context(
            default_folder_id=self.folder_a_a.id,
            default_owner_id=self.doc_user.id,
        ).create([
            {
                'name': 'defaults',
            },
            {
                'name': 'Company document',
                'user_folder_id': 'COMPANY',
            }, {
                'name': 'My Drive Document',
                'user_folder_id': 'MY',
            }, {
                'name': 'Folder A/B',
                'type': 'folder',
                'user_folder_id': str(self.folder_a.id),
            }, {
                'name': 'Document A/B2',
                'folder_id': self.folder_a.id,
                'user_folder_id': str(self.folder_a.id),
            }
        ])
        self.assertEqual(defaults.folder_id.id, self.folder_a_a.id)
        self.assertEqual(defaults.owner_id.id, self.doc_user.id)
        self.assertFalse(company.folder_id)
        self.assertFalse(company.owner_id)
        self.assertFalse(my.folder_id)
        self.assertEqual(my.owner_id, self.internal_user)  # user_folder_id=MY primes over context defaults
        self.assertEqual(folder_a_b.folder_id, self.folder_a)
        self.assertEqual(folder_a_b.owner_id, self.doc_user)  # context default used
        self.assertEqual(folder_a_b_2.folder_id, self.folder_a)

        for user_folder_id in ('ALL', 'RECENT', 'SHARED', 'TRASH'):
            with self.subTest(user_folder_id=user_folder_id):
                with self.assertRaises(UserError):
                    self.env['documents.document'].create({
                        'name': 'Should fail',
                        'user_folder_id': user_folder_id,
                    })
        for idx, values in enumerate((
            {'user_folder_id': str(self.folder_a_a.id), 'folder_id': self.folder_a.id},  # different folder_id
            {'user_folder_id': 'COMPANY', 'folder_id': self.folder_a.id},  # Company has folder_id=False
            {'user_folder_id': 'COMPANY', 'owner_id': self.internal_user.id},  # Company has owner_id=False
        )):
            with self.subTest(idx=idx):
                with self.subTest(kind='create'), self.assertRaises(UserError):
                    self.env['documents.document'].create(values)
                with self.subTest(kind='write'), self.assertRaises(UserError):
                    my.write(values)

    @users('internal_user')
    def test_search_child_of(self):
        my_subfolder, company_subfolder, sub_sub_company_admin = self.env["documents.document"].sudo().create([
            {'name': 'My Subfolder', 'folder_id': self.internal_drive.id},
            {'name': 'Company Subfolder', 'type': 'folder', 'folder_id': self.company_folder.id},
            {
                'name': 'Sub Company Admin Folder',
                'type': 'folder',
                'access_internal': 'view',
                'folder_id': self.sub_company_admin.id,
            },
        ])
        sub_company_admin_folder_doc = self.env['documents.document'].create({
            'name': 'Sub Company Admin Folder Doc',
            'access_internal': 'view',
            'folder_id': sub_sub_company_admin.id,
        })
        cases = [
            ('SHARED',
             self.folder_a | self.folder_a_a | self.folder_b | self.shared_doc_company_sub | self.shared_doc_drive
             | self.shared_doc_company | sub_sub_company_admin | sub_company_admin_folder_doc),
            ('MY', self.internal_drive | my_subfolder),
            ('COMPANY', self.company_folder | company_subfolder | self.company_doc),
            (str(self.internal_drive.id), my_subfolder),
        ]
        accessible_documents = self.env["documents.document"].search([])
        for user_folder_id, expected in cases:
            with self.subTest(user_folder_id=user_folder_id):
                domain = [('user_folder_id', 'child_of', user_folder_id)]
                actual = self.env['documents.document'].search(domain)
                self.assertDocumentsEqual(actual, expected)
                filtered = accessible_documents.filtered_domain(domain)
                self.assertDocumentsEqual(filtered, expected)

    @users('internal_user')
    def test_search_folder_id_child_of(self):
        my_subfolder, company_subfolder = self.env['documents.document'].create([
            {'name': 'My Subfolder', 'folder_id': self.internal_drive.id},
            {'name': 'Company Subfolder', 'type': 'folder', 'folder_id': self.company_folder.id},
        ])
        cases = [
            (self.internal_drive, self.internal_drive | my_subfolder),  # not shared_doc_drive
            (self.company_folder, self.company_folder | company_subfolder)  # not shared_doc_company_sub
        ]
        accessible_documents = self.env["documents.document"].search([])
        for folder, expected in cases:
            with self.subTest(folder=folder.name):
                domain = [('folder_id', 'child_of', folder.id)]
                actual = self.env['documents.document'].search(domain)
                self.assertDocumentsEqual(actual, expected)
                filtered = accessible_documents.filtered_domain(domain)
                self.assertDocumentsEqual(filtered, expected)

    def test_compute_and_search_user_folder_id_equal(self):
        """Test user_folder_id's compute and search with "equal" operator.

        Cases are shaped as [(user, expected), ...], where:
            user: test user,
            expected: records per user_folder_id value, such that
              * searching for this value (if truthy) should retrieve these records
              * computing user_folder_id for the records is correct ('False' for inaccessible docs)
        """
        Document = self.env['documents.document']
        cases = [
            (self.internal_user, {
                'COMPANY': self.company_doc | self.company_folder,
                'MY': self.internal_drive,
                'SHARED': self.folder_a | self.folder_b | self.shared_doc_company_sub | self.shared_doc_drive | self.shared_doc_company,
                'RECENT': self.internal_drive | self.folder_a,
                str(self.folder_a.id): self.folder_a_a,
                False: self.company_restr_doc | self.company_restr_folder | self.sub_company_admin | self.sub_drive_admin
            }),
            (self.doc_user, {
                'COMPANY': self.company_doc | self.company_folder | self.company_restr_doc,
                'MY': self.folder_a | self.folder_b,
                'SHARED': self.shared_doc_company_sub | self.shared_doc_drive | self.shared_doc_company,
                'RECENT': self.folder_a | self.folder_a_a | self.folder_b,
                str(self.folder_a.id): self.folder_a_a,
                False: self.internal_drive | self.sub_company_admin | self.sub_drive_admin,
            }),
            (self.portal_user, {
                'COMPANY': Document,
                'MY': Document,
                'SHARED': self.folder_a,
                'RECENT': self.folder_a,
                str(self.folder_a.id): self.folder_a_a,
                False: self.test_documents - self.folder_a_a,
            }),
            (self.document_sys_admin, {
                'COMPANY': self.company_doc | self.company_restr_doc | self.company_folder | self.company_restr_folder,
                'MY': Document,
                'SHARED': self.internal_drive | self.folder_a | self.folder_b,
                'RECENT': self.folder_a,
                str(self.folder_a.id): self.folder_a_a,
                str(self.company_folder.id): self.sub_company_admin,
                str(self.internal_drive.id): self.sub_drive_admin,
                str(self.company_restr_folder.id): self.shared_doc_company,
                str(self.sub_drive_admin.id): self.shared_doc_drive,
            }),
        ]
        for user, expected in cases:
            for user_folder_id, documents in expected.items():
                with self.subTest(user=user.name, user_folder_id=user_folder_id):
                    if user_folder_id:
                        actual = self.env['documents.document'].with_user(user).search(
                            Domain('user_folder_id', '=', user_folder_id))
                        self.assertDocumentsEqual(actual, documents)
                    # Test compute except for no records or search-only results
                    if (
                        documents
                        and user_folder_id != 'RECENT'
                        and (user_folder_id != 'SHARED' or user != self.portal_user)
                    ):
                        self.assertEqual(set(documents.with_user(user).mapped('user_folder_id')), {user_folder_id})

    @users('internal_user')
    def test_search_user_folder_id_in_and_not_in(self):
        to_find_all = ['COMPANY', 'MY', 'SHARED', str(self.folder_a.id)]
        expected_all = self.company_doc | self.company_folder | self.internal_drive | self.folder_a | self.folder_a_a \
            | self.folder_b | self.shared_doc_company_sub | self.shared_doc_drive | self.shared_doc_company
        actual = self.env['documents.document'].search([('user_folder_id', 'in', to_find_all)])
        self.assertDocumentsEqual(actual, expected_all)

        expected_company = self.company_doc | self.company_folder
        actual_company = self.env['documents.document'].search([('user_folder_id', 'in', 'COMPANY')])
        self.assertDocumentsEqual(actual_company, expected_company)

        expected_not_company = expected_all - expected_company
        actual_not_company = self.env['documents.document'].search([('user_folder_id', 'not in', 'COMPANY')])
        self.assertDocumentsEqual(actual_not_company, expected_not_company)

        expected_my = self.internal_drive
        actual_my = self.env['documents.document'].search([('user_folder_id', 'in', 'MY')])
        self.assertDocumentsEqual(actual_my, expected_my)

        expected_not_my = expected_all - expected_my
        actual_not_my = self.env['documents.document'].search([('user_folder_id', 'not in', 'MY')])
        self.assertDocumentsEqual(actual_not_my, expected_not_my)

        expected_shared = self.folder_a | self.folder_b | self.shared_doc_company_sub | self.shared_doc_drive | self.shared_doc_company
        actual_shared = self.env['documents.document'].search([('user_folder_id', 'in', 'SHARED')])
        self.assertDocumentsEqual(actual_shared, expected_shared)

        expected_not_shared = expected_all - expected_shared
        actual_not_shared = self.env['documents.document'].search([('user_folder_id', 'not in', 'SHARED')])
        self.assertDocumentsEqual(actual_not_shared, expected_not_shared)

        expected_folder_a = self.folder_a_a
        actual_folder_a = self.env['documents.document'].search([('user_folder_id', 'in', str(self.folder_a.id))])
        self.assertDocumentsEqual(actual_folder_a, expected_folder_a)

        expected_not_folder_a = expected_all - expected_folder_a
        actual_not_folder_a = self.env['documents.document'].search([('user_folder_id', 'not in', str(self.folder_a.id))])
        self.assertDocumentsEqual(actual_not_folder_a, expected_not_folder_a)

    def test_documents_search_panel(self):
        cases = [
            (
                {},
                {
                    "Company": None,
                    "Company Admin Subfolder": self.company_folder.id,
                    "Company Folder": "COMPANY",
                    "Company Restricted Folder": "COMPANY",
                    "Drive Admin Subfolder": self.internal_drive.id,
                    "Internal User's Drive Document": "SHARED",
                    "My Drive": None,
                    "Recent": None,
                    "Shared with me": None,
                    "Trash": None,
                    "folder A": "SHARED",
                    "folder A - A": self.folder_a.id,
                    "folder B": "SHARED",
                },
            ),
            (
                {"documents_unique_folder_id": self.folder_a.id},
                {
                    "folder A": False,
                    "folder A - A": self.folder_a.id,
                },
            ),
        ]
        for context, expected in cases:
            with self.subTest(context=context):
                Documents = self.env['documents.document'].with_context(context)
                actual = Documents.search_panel_select_range("user_folder_id")['values']
                user_folder_ids = {vals["display_name"]: vals.get("user_folder_id") for vals in actual}
                self.assertEqual(user_folder_ids, expected)
