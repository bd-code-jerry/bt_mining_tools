from concurrent.futures import ThreadPoolExecutor
from threading import Event, local
from unittest.mock import patch
import sqlite3
from pathlib import Path
from backend.app.database import db_connection
from backend.app.features.balances import service
from tests.support import AuthenticatedWorkspaceTestCase, create_legacy_database
from backend.app.core.database import migrate_path


class BalanceAdditionsTests(AuthenticatedWorkspaceTestCase):
    def topup(self, additions=None, date='2035-01-02', workspace=None):
        return self.client.post('/api/balances/add-balance', params={'workspace_id': workspace or self.shared_id},
                                json={'entry_date': date, 'additions': additions or {'openrouter': 2.123456789}})

    def overview(self, **params):
        return self.client.get('/api/balances/overview', params={'workspace_id': self.shared_id, **params}).json()

    def test_topups_have_real_metadata_and_separate_pagination(self):
        legacy_id = self.add_history(self.shared_id, '2035-01-01')
        first = self.topup({'openrouter': 2.123456789, 'chutes': 10}).json()['entry']
        self.topup(date='2035-01-03')
        data = self.overview(page_size=1, topup_page=2, topup_page_size=1)
        self.assertEqual([e['id'] for e in data['history']], [legacy_id])
        self.assertEqual(data['pagination']['total_items'], 1)
        self.assertEqual(data['topup_pagination']['total_items'], 2)
        self.assertEqual(data['topup_history'][0]['id'], first['id'])
        self.assertEqual(first['entry_kind'], 'topup')
        values = {v['provider_key']: v for v in first['values']}
        self.assertEqual(values['openrouter']['balance_before'], 18)
        self.assertEqual(values['openrouter']['added_balance'], 2.123456789)
        self.assertEqual(values['openrouter']['left_balance'], 20.123456789)
        self.assertEqual(values['chutes']['unit'], 't')
        self.assertEqual(values['chutes']['added_balance'], 10)
        self.assertEqual(values['parallel']['added_balance'], 0)
        self.assertEqual(data['summary']['by_unit']['USD'], 2)
        self.assertEqual(data['latest']['entry_kind'], 'topup')

    def test_legacy_is_honest_and_classification_validates_actual_amount(self):
        legacy_id = self.add_history(self.shared_id, '2035-01-01', total=20, used=0, left=20)
        data = self.overview()
        self.assertEqual(data['history'][0]['entry_kind'], 'legacy')
        self.assertIsNone(data['history'][0]['values'][0]['added_balance'])
        path = f'/api/balances/add-balance/{legacy_id}'
        params = {'workspace_id': self.shared_id}
        rejected = self.client.put(path, params=params, json={'additions': {'openrouter': 21}})
        self.assertEqual(rejected.status_code, 422)
        classified = self.client.put(path, params=params, json={'additions': {'openrouter': 3.25}})
        self.assertEqual(classified.status_code, 200, classified.text)
        value = classified.json()['entry']['values'][0]
        self.assertEqual(value['balance_before'], 16.75)
        self.assertEqual(value['left_balance'], 20)
        self.assertEqual(self.overview()['history'], [])
        self.assertEqual(len(self.overview()['topup_history']), 1)

    def test_classification_rejects_usage_and_unknown_providers_atomically(self):
        legacy_id = self.add_history(self.shared_id, '2035-01-01')
        response = self.client.put(f'/api/balances/add-balance/{legacy_id}', params={'workspace_id': self.shared_id},
                                   json={'additions': {'openrouter': 1}})
        self.assertEqual(response.status_code, 422)
        response = self.topup({'unknown': 5})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.overview()['pagination']['total_items'], 1)

    def test_topup_edits_preserve_before_and_generic_edits_are_rejected(self):
        self.add_history(self.shared_id, '2035-01-01')
        entry = self.topup().json()['entry']
        path = f"/api/balances/add-balance/{entry['id']}"
        params = {'workspace_id': self.shared_id}
        response = self.client.put(path, params=params, json={'entry_date': '2035-01-04', 'additions': {'openrouter': 4.987654321}})
        self.assertEqual(response.status_code, 200, response.text)
        value = next(v for v in response.json()['entry']['values'] if v['provider_key'] == 'openrouter')
        self.assertEqual(value['balance_before'], 18)
        self.assertEqual(value['added_balance'], 4.987654321)
        self.assertEqual(value['left_balance'], 22.987654321)
        rejected = self.client.put(f"/api/balances/history/{entry['id']}", params=params, json={'values': {}})
        self.assertEqual(rejected.status_code, 409)
        invalid = self.client.put(path, params=params, json={'entry_date': '2035-02-01', 'additions': {'openrouter': -1}})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.overview()['topup_history'][0]['entry_date'], '2035-01-04')
        self.assertEqual(self.client.delete(f"/api/balances/history/{entry['id']}", params=params).status_code, 200)
        self.assertEqual(self.overview()['topup_history'], [])
        with db_connection() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM history_values WHERE entry_id=?', (entry['id'],)).fetchone()[0], 0)

    def test_classifying_an_ordinary_update_is_rejected(self):
        created = self.client.post('/api/balances/history', params={'workspace_id': self.shared_id},
                                   json={'expected_latest_entry_id': None, 'entry_date': '2035-01-01', 'values': {}}).json()['entry']
        self.assertEqual(created['entry_kind'], 'balance')
        response = self.client.put(f"/api/balances/add-balance/{created['id']}", params={'workspace_id': self.shared_id}, json={'additions': {'openrouter': 1}})
        self.assertEqual(response.status_code, 409)

    def test_topup_corrections_enforce_workspace_permissions(self):
        entry = self.topup(workspace=self.other_workspace_id).json()['entry']
        self.set_actor_role('user')
        response = self.client.put(f"/api/balances/add-balance/{entry['id']}", params={'workspace_id': self.other_workspace_id}, json={'additions': {'openrouter': 1}})
        self.assertEqual(response.status_code, 403)
        response = self.client.put(f"/api/balances/add-balance/{entry['id']}", params={'workspace_id': self.own_workspace_id}, json={'additions': {'openrouter': 1}})
        self.assertEqual(response.status_code, 404)
        self.set_actor_role('member')
        self.assertEqual(self.topup().status_code, 403)
        self.assertEqual(self.client.put(f"/api/balances/add-balance/{entry['id']}", json={'additions': {'openrouter': 1}}).status_code, 403)

    def test_negative_fractional_additions_are_rejected_without_changes(self):
        self.add_history(self.shared_id, '2035-01-01')
        response = self.topup({'openrouter': 2, 'parallel': -0.00000001})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.overview()['topup_history'], [])

    def test_legacy_partial_provider_snapshot_remains_editable(self):
        entry_id = self.add_history(self.shared_id, '2035-01-01')
        response = self.client.put(f'/api/balances/history/{entry_id}', params={'workspace_id': self.shared_id},
            json={'values': {'openrouter': {'total': 20, 'used': 3, 'left': 17}, 'parallel': {'total':0,'used':0,'left':0}}})
        self.assertEqual(response.status_code, 200, response.text)
        values = {v['provider_key']: v for v in response.json()['entry']['values']}
        self.assertEqual(values['openrouter']['used_balance'], 3)
        self.assertEqual(values['parallel']['left_balance'], 0)
        self.assertEqual(response.json()['entry']['entry_kind'], 'legacy')

    def test_pre_upgrade_snapshot_survives_restart_without_invented_additions(self):
        path = Path(self.temp_dir.name) / 'legacy.sqlite3'
        legacy = create_legacy_database(path)
        migrate_path(path, initial_admin_username='root')
        migrate_path(path, initial_admin_username='root')
        with sqlite3.connect(path) as conn:
            row = conn.execute('SELECT entry_kind FROM history_entries WHERE id=?', (legacy['entry_id'],)).fetchone()
            values = conn.execute('SELECT total_balance, used_balance, left_balance, added_balance, balance_before FROM history_values WHERE id=?', (legacy['value_id'],)).fetchone()
        self.assertEqual(row[0], 'legacy')
        self.assertEqual(values, (20, 3.5, 16.5, None, None))

    def test_generic_edit_and_legacy_classification_cannot_race_to_corrupt_metadata(self):
        entry_id = self.add_history(self.shared_id, '2035-01-01', total=20, used=0, left=20)
        original_get = service.get_history_entry
        worker = local()
        generic_read = Event()
        release_edit = Event()
        classification_read = Event()

        def observed_get(conn, entry_id, workspace_id):
            entry = original_get(conn, entry_id, workspace_id)
            if getattr(worker, 'label', None) == 'edit' and not generic_read.is_set():
                generic_read.set()
                if not release_edit.wait(timeout=5):
                    raise TimeoutError('edit not released')
            elif getattr(worker, 'label', None) == 'classify':
                classification_read.set()
            return entry

        def edit():
            worker.label = 'edit'
            with db_connection() as conn:
                service.update_history_entry(conn, entry_id, self.actor_id,
                    {'values': {'openrouter': {'total':20,'used':0,'left':20}}}, workspace_id=self.shared_id)

        def classify():
            worker.label = 'classify'
            with db_connection() as conn:
                service.update_add_balance_entry(conn, entry_id, self.actor_id,
                    {'additions': {'openrouter':3}}, workspace_id=self.shared_id)

        with patch.object(service, 'get_history_entry', observed_get):
            with ThreadPoolExecutor(max_workers=2) as pool:
                editing = pool.submit(edit)
                self.assertTrue(generic_read.wait(timeout=5))
                classifying = pool.submit(classify)
                classified_before_edit_committed = classification_read.wait(timeout=0.2)
                release_edit.set()
                editing.result(timeout=5)
                classifying.result(timeout=5)
        self.assertFalse(classified_before_edit_committed)
        entry = self.overview()['topup_history'][0]
        self.assertEqual(entry['values'][0]['added_balance'], 3)
        self.assertEqual(entry['values'][0]['balance_before'], 17)
