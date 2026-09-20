from odoo.addons.documents_account.tests.common import DocumentsAccountTestCommon
from odoo.tests.common import RecordCapturer, tagged


@tagged('post_install', '-at_install', 'test_document_bridge')
class TestJournalSyncAutoConfig(DocumentsAccountTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        FolderSettings = cls.env['documents.account.folder.setting']
        cls.setup_other_company()

        # Delete existing settings to test their creation except for cash journal
        existing_settings = FolderSettings.search([('journal_id', 'any', [('type', 'in', ['bank', 'general'])])])
        auto_configured_folders = existing_settings.folder_id
        existing_settings.unlink()
        auto_configured_folders.action_archive()

        # Setup translation to test the translation
        cls.env['res.lang']._activate_lang('fr_FR')
        journal_type_sel_by_value = cls.env['ir.model.fields']._get(
            'account.journal', 'type').selection_ids.grouped('value')
        for journal_type, default_tr, fr_FR_tr in (
                ('general', 'Miscellaneous', 'Divers'),
                ('bank', 'Bank', 'Banque'),
                ('cash', 'Cash', 'Espèces'),
        ):
            journal_type_sel_by_value[journal_type].name = default_tr
            journal_type_sel_by_value[journal_type].with_context(lang='fr_FR').name = fr_FR_tr

        # Setup journals which will automatically create the synchronization settings
        cls.company_2 = cls.env['res.company'].search([('name', '=', 'company_2')])[0]
        with cls._freeze_time('2022-08-22 09:16'):
            cls.journals = cls.env['account.journal'].create([
                {'name': 'Misc company 1', 'type': 'general', 'company_id': cls.env.company.id},
                {'name': 'Misc company 2', 'type': 'general', 'company_id': cls.company_2.id},
                {'name': 'Bank company 2', 'type': 'bank', 'company_id': cls.company_2.id},
                {'name': 'Cash company 1', 'type': 'cash', 'company_id': cls.env.company.id},
            ])
        for journal, translation in zip(cls.journals, (
            'Divers companie 1', 'Divers companie 2', 'Banque companie 2', 'Espèce companie 1'
        )):
            journal.with_context(lang='fr_FR').name = translation
        settings = FolderSettings.search([('journal_id', 'in', cls.journals.ids)])
        cls.settings_by_name = settings.grouped(lambda j: j.journal_id.name)
        cls.unused_folder_with_misc_name = cls.env['documents.document'].create({
            'name': 'Miscellaneous', 'type': 'folder',
            'folder_id': cls.env.company.account_folder_id.id, 'company_id': cls.env.company.id})
        cls.misc_journal = cls.journals[0]
        cls.misc_setting = FolderSettings.search([('journal_id', '=', cls.misc_journal.id)])
        cls.misc_folder = cls.misc_setting.folder_id

    def test_initial_data(self):
        self.assertEqual(len(self.settings_by_name), 4)
        self.assertNotEqual(self.env.lang, 'fr_FR')

    def test_auto_creation_of_settings(self):
        """Test the creation of the documents synchronization settings when creating journals."""
        for name, expected_folder_name, expected_folder_name_fr, expected_company in (
            ('Misc company 1', 'Miscellaneous', 'Divers', self.env.company),
            ('Misc company 2', 'Miscellaneous', 'Divers', self.company_2),
            ('Bank company 2', 'Bank', 'Banque', self.company_2),
            # The name of the folder is only in English as it was created before the language activation
            ('Cash company 1', 'Cash', 'Cash', self.env.company),
        ):
            setting = self.settings_by_name[name]
            folder = setting.folder_id
            self.assertEqual(folder.name, expected_folder_name)
            self.assertEqual(folder.with_context(lang='fr_FR').name, expected_folder_name_fr)
            self.assertEqual(folder.company_id, expected_company)
            self.assertFalse(folder.owner_id)
            self.assertEqual(folder.access_internal, 'edit')
            self.assertEqual(folder.access_via_link, 'none')
            self.assertFalse(folder.access_ids.filtered(lambda a: a.role))
            self.assertEqual(setting.company_id, expected_company)
            self.assertEqual(setting.mapped('tag_ids.name'), [name])
            self.assertEqual(setting.with_context(lang='fr_FR').mapped('tag_ids.name'), [name])

    def test_create_journal_without_base_folder(self):
        """Test that we can still create journal without account_folder_id set on the company."""
        self.env.company.account_folder_id = False
        journal = self.env['account.journal'].create(
            {'name': 'Test without base folder', 'type': 'general', 'company_id': self.env.company.id})
        self.assertFalse(self.env['documents.account.folder.setting'].search([('journal_id', '=', journal.id)]))

    def test_folder_creation(self):
        """Test that a folder is created if there are no settings for the journal type nor existing suitable folder."""
        FolderSettings = self.env['documents.account.folder.setting']
        self.misc_setting.unlink()
        (self.misc_folder | self.unused_folder_with_misc_name).unlink()

        with RecordCapturer(self.env['documents.document'], []) as capture:
            misc = self.env['account.journal'].create({'name': 'Misc', 'type': 'general'})
        created_folder = capture.records.filtered(lambda d: d.name == 'Miscellaneous')
        self.assertEqual(len(created_folder), 1)
        self.assertEqual(FolderSettings.search([('journal_id', '=', misc.id)]).folder_id, created_folder)

    def test_folder_creation_existing_folder_with_wrong_company(self):
        """Test that a folder with the wrong company is not used when creating journals."""
        FolderSettings = self.env['documents.account.folder.setting']
        self.misc_setting.unlink()
        self.misc_folder.unlink()
        self.unused_folder_with_misc_name.company_id = False

        with RecordCapturer(self.env['documents.document'], []) as capture:
            misc = self.env['account.journal'].create({'name': 'Misc', 'type': 'general'})
        created_folder = capture.records.filtered(lambda d: d.name == 'Miscellaneous')
        self.assertEqual(len(created_folder), 1)
        self.assertEqual(FolderSettings.search([('journal_id', '=', misc.id)]).folder_id, created_folder)

    def test_folder_reuse_from_settings(self):
        """Test the reuse of folder from existing settings with the same journal type (and company)."""
        FolderSettings = self.env['documents.account.folder.setting']
        self.misc_setting.folder_id.name = 'renamed'

        with self._freeze_time('2024-08-22 09:16'):
            new_misc_journal = self.env['account.journal'].create({'name': 'Misc 2', 'type': 'general'})
        new_misc_setting = FolderSettings.search([('journal_id', '=', new_misc_journal.id)])
        self.assertEqual(new_misc_setting.folder_id, self.misc_setting.folder_id,
                         "The folder of the configuration with the same journal type is used (same comapny).")
        # If multiple configurations for the journal type exist we take the folder of the more recent one
        replaced_folder = self.env['documents.document'].create({
            'name': 'replaced', 'type': 'folder',
            'folder_id': self.env.company.account_folder_id.id, 'company_id': self.env.company.id})
        new_misc_setting.folder_id = replaced_folder
        with self._freeze_time('2025-08-22 10:16'):
            another_misc_journal = self.env['account.journal'].create({'name': 'Misc 3', 'type': 'general'})
        another_misc_setting = FolderSettings.search([('journal_id', '=', another_misc_journal.id)])
        self.assertEqual(another_misc_setting.folder_id.name, 'replaced')
        self.assertEqual(new_misc_setting.folder_id.name, 'replaced')
        self.assertEqual(self.misc_setting.folder_id.name, 'renamed')
        self.assertFalse(
            FolderSettings.search([('folder_id', '=', self.unused_folder_with_misc_name.id)]),
            "The folder with the journal type name is not used as existing configured folder are preferred.")

    def test_folder_reuse_no_setting(self):
        """Test that an existing folder with the right name is used if there are no settings for the journal type."""
        FolderSettings = self.env['documents.account.folder.setting']
        self.misc_setting.unlink()
        self.misc_folder.unlink()

        misc_journal_no_pre_config = self.env['account.journal'].create({'name': 'Misc', 'type': 'general'})
        misc_journal_no_pre_config_setting = FolderSettings.search([('journal_id', '=', misc_journal_no_pre_config.id)])
        self.assertEqual(misc_journal_no_pre_config_setting.folder_id.name, 'Miscellaneous')
        self.assertEqual(misc_journal_no_pre_config_setting.folder_id, self.unused_folder_with_misc_name)

    def test_post_init(self):
        """Simulate the creation of the documents synchronization settings in the post init of documents_account."""
        # Remove all settings and related folders/tags as if we were installing documents_account
        FolderSettings = self.env['documents.account.folder.setting']
        settings = FolderSettings.search([])
        folders = settings.folder_id
        tags = settings.tag_ids
        self.unused_folder_with_misc_name.unlink()
        settings.unlink()
        folders.unlink()
        tags.unlink()

        for lang in (self.env.lang, 'fr_FR'):
            with self.subTest(lang=lang):
                self.env['account.journal'].with_context(lang=lang).search(
                    [('id', 'not in', FolderSettings._search([]).select("journal_id"))]
                )._documents_configure_sync()
                settings_by_name = FolderSettings.search(
                    [('journal_id', 'in', self.journals.ids)]).grouped(lambda j: j.journal_id.name)
                for name, expected_tag_name_fr, expected_folder_name, expected_folder_name_fr, expected_company in (
                        ('Misc company 1', 'Divers companie 1', 'Miscellaneous', 'Divers', self.env.company),
                        ('Misc company 2', 'Divers companie 2', 'Miscellaneous', 'Divers', self.company_2),
                        ('Bank company 2', 'Banque companie 2', 'Bank', 'Banque', self.company_2),
                        ('Cash company 1', 'Espèce companie 1', 'Cash', 'Espèces', self.env.company),
                ):
                    expected_tag_name = name
                    setting = settings_by_name[name]
                    folder = setting.folder_id
                    self.assertEqual(folder.name, expected_folder_name)
                    self.assertEqual(folder.with_context(lang='fr_FR').name, expected_folder_name_fr)
                    self.assertEqual(folder.company_id, expected_company)
                    self.assertFalse(folder.owner_id)
                    self.assertEqual(folder.access_internal, 'edit')
                    self.assertEqual(folder.access_via_link, 'none')
                    self.assertFalse(folder.access_ids.filtered(lambda a: a.role))
                    self.assertEqual(setting.company_id, expected_company)
                    self.assertEqual(setting.mapped('tag_ids.name'), [expected_tag_name])
                    self.assertEqual(setting.with_context(lang='fr_FR').mapped('tag_ids.name'), [expected_tag_name_fr])
