-- disable bank synchronisation links
UPDATE account_online_link
   SET client_id = 'duplicate';
