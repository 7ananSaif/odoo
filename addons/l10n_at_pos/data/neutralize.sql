UPDATE res_company
   SET l10n_at_fiskaly_api_key = 'dummy_value',
       l10n_at_fiskaly_api_secret = 'dummy_value',
       l10n_at_fiskaly_access_token = 'dummy_value',
       l10n_at_fiskaly_organization_id = 'dummy_value'
   WHERE l10n_at_fiskaly_access_token IS NOT NULL;
