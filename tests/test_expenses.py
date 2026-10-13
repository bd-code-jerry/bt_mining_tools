from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.database import db_connection
from tests.support import AuthenticatedWorkspaceTestCase


class ExpenseLedgerTests(AuthenticatedWorkspaceTestCase):
    def participants(self):
        response = self.client.get('/api/expenses/participants')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['participants']

    def category(self, name='VPS', parent_id=None):
        response = self.client.post('/api/expenses/categories', json={'name': name, 'parent_id': parent_id})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['category']

    def account(self, name, role='user'):
        response = self.client.post('/api/users', json={'username': name, 'email': name+'@example.com',
            'password': 'strong-password-1', 'role': role})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['user']

    def cost_payload(self, selected_category_id, participants, **changes):
        payload = {'amount': '100', 'expense_date': '2026-10-01', 'category_id': selected_category_id,
            'note': 'Hosting', 'participant_ids': participants, 'request_id': 'test-expense'}
        payload.update(changes)
        return payload

    def save_cost(self, payload):
        response = self.client.post('/api/expenses/costs', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['cost']

    def test_exact_even_and_uneven_allocations_persist_across_connections(self):
        category = self.category()
        ids = [p['id'] for p in self.participants()]
        even = self.save_cost(self.cost_payload(category['id'], list(reversed(ids))))
        self.assertEqual([a['share_cents'] for a in even['allocations']], [5000, 5000])
        self.account('third-person', 'member')
        ids = [p['id'] for p in self.participants()]
        odd = self.save_cost(self.cost_payload(category['id'], list(reversed(ids)), request_id='odd'))
        self.assertEqual([a['share_cents'] for a in odd['allocations']], [3334, 3333, 3333])
        with TestClient(self.client.app) as restarted:
            restarted.cookies.update(self.client.cookies)
            saved = restarted.get('/api/expenses/costs').json()['costs']
        self.assertEqual(len(saved), 2)
        self.assertEqual(sum(a['share_cents'] for a in saved[0]['allocations']), 10000)
        self.assertEqual(self.client.get('/api/expenses/summary').json()['spent_cents'], 20000)

    def test_retry_is_idempotent_but_changed_payload_conflicts(self):
        payload = self.cost_payload(self.category()['id'], [p['id'] for p in self.participants()])
        first = self.save_cost(payload)
        self.assertEqual(self.save_cost(payload)['id'], first['id'])
        payload['amount'] = '101'
        self.assertEqual(self.client.post('/api/expenses/costs', json=payload).status_code, 409)
        self.assertEqual(self.client.get('/api/expenses/costs').json()['pagination']['total_items'], 1)

    def test_validation_rejects_bad_money_dates_and_duplicate_or_ineligible_people_atomically(self):
        category = self.category()
        ids = [p['id'] for p in self.participants()]
        for change in ({'amount': '0'}, {'amount': '-1'}, {'amount': '1.001'}, {'amount': 'NaN'},
                       {'amount': '1e2'}, {'amount': '92233720368547758.08'}, {'expense_date': '2026-02-30'},
                       {'expense_date': '2026-1-1'}, {'participant_ids': []}, {'participant_ids': ids+ids},
                       {'participant_ids': [987654]}, {'category_id': 987654}, {'amount': 1.2}):
            with self.subTest(change=change):
                response = self.client.post('/api/expenses/costs', json=self.cost_payload(category['id'], ids, **change))
                self.assertEqual(response.status_code, 422, response.text)
        with db_connection() as conn:
            conn.execute("UPDATE users SET status='disabled' WHERE id=?", (self.other_user_id,))
        response = self.client.post('/api/expenses/costs', json=self.cost_payload(category['id'], ids))
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get('/api/expenses/summary').json()['spent_cents'], 0)
        with db_connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM expense_allocations').fetchone()[0], 0)

    def test_categories_optional_nesting_uniqueness_cycles_and_archival(self):
        parent = self.category(' VPS ')
        child = self.category('Hetzner', parent['id'])
        leaf = self.category('Compute', child['id'])
        self.assertEqual(leaf['path'], 'VPS / Hetzner / Compute')
        self.assertEqual(self.client.post('/api/expenses/categories', json={'name': 'vPs'}).status_code, 409)
        self.assertEqual(self.client.post('/api/expenses/categories', json={'name': 'HETZNER', 'parent_id': parent['id']}).status_code, 409)
        self.assertEqual(self.client.post('/api/expenses/categories', json={'name': ' '}).status_code, 422)
        self.assertEqual(self.client.patch(f"/api/expenses/categories/{parent['id']}", json={'parent_id': leaf['id']}).status_code, 422)
        ids = [p['id'] for p in self.participants()]
        cost = self.save_cost(self.cost_payload(child['id'], ids))
        self.assertEqual(self.client.patch(f"/api/expenses/categories/{parent['id']}", json={'name': 'Servers', 'archived': True}).status_code, 200)
        categories = self.client.get('/api/expenses/categories').json()['categories']
        self.assertTrue(next(c for c in categories if c['id']==child['id'])['effective_archived'])
        self.assertEqual(self.client.post('/api/expenses/costs', json=self.cost_payload(child['id'], ids, request_id='blocked')).status_code, 422)
        self.assertEqual(self.client.get('/api/expenses/costs').json()['costs'][0]['category_path'], 'VPS / Hetzner')
        self.assertEqual(self.client.post('/api/expenses/categories', json={'name': 'New', 'parent_id': parent['id']}).status_code, 422)
        self.assertEqual(self.client.get('/api/expenses/people', params={'category_id':parent['id']}).json()['total_cents'], cost['amount_cents'])

    def test_combined_filters_descendants_and_pagination_independent_totals(self):
        parent = self.category()
        child = self.category('Hetzner', parent['id'])
        unrelated = self.category('API key')
        participants = self.participants()
        ids = [p['id'] for p in participants]
        target = next(p for p in participants if p['user_id']==self.other_user_id)
        for index, (category, day) in enumerate(((parent,'2026-10-01'), (child,'2026-10-02'), (child,'2026-10-03'), (unrelated,'2026-10-02'), (child,'2026-09-30'))):
            self.save_cost(self.cost_payload(category['id'], ids, expense_date=day, request_id=f'filter-{index}'))
        filters = {'q':'OTHER', 'category_id':parent['id'], 'period':'custom', 'start_date':'2026-10-01', 'end_date':'2026-10-03'}
        people = self.client.get('/api/expenses/people', params=filters).json()
        self.assertEqual([(p['id'],p['total_cents']) for p in people['people']], [(target['id'],15000)])
        self.assertEqual(people['total_cents'],15000)
        costs = self.client.get('/api/expenses/costs', params={**filters,'participant_id':target['id'],'page_size':1}).json()
        self.assertEqual(costs['filtered_total_cents'],15000)
        self.assertEqual(costs['pagination']['total_items'],3)
        self.assertEqual(costs['costs'][0]['allocated_cents'],5000)
        self.assertEqual(costs['costs'][0]['amount_cents'],10000)
        whole = self.client.get('/api/expenses/costs', params={'category_id':parent['id']}).json()
        self.assertEqual(whole['filtered_total_cents'],40000)
        self.assertEqual(self.client.get('/api/expenses/summary').json()['spent_cents'],50000)
        self.assertEqual(self.client.get('/api/expenses/people', params={**filters,'start_date':'2026-10-04'}).status_code,422)
        self.assertEqual(self.client.get('/api/expenses/people', params={'period':'custom'}).status_code,422)

    def test_historical_identity_survives_account_deletion_and_name_reuse(self):
        category = self.category()
        participants = self.participants()
        other = next(p for p in participants if p['user_id']==self.other_user_id)
        self.save_cost(self.cost_payload(category['id'], [p['id'] for p in participants]))
        with db_connection() as conn:
            conn.execute("UPDATE users SET status='disabled' WHERE id=?", (self.other_user_id,))
        people = self.client.get('/api/expenses/people').json()['people']
        self.assertEqual(next(p for p in people if p['id']==other['id'])['status'],'disabled')
        self.assertEqual(self.client.delete(f'/api/users/{self.other_user_id}').status_code,200)
        deleted = next(p for p in self.participants() if p['id']==other['id'])
        self.assertEqual((deleted['user_id'],deleted['status'],deleted['eligible']), (None,'deleted',False))
        replacement = self.account('other-user')
        current = next(p for p in self.participants() if p['user_id']==replacement['id'])
        self.assertNotEqual(current['id'],other['id'])
        people = self.client.get('/api/expenses/people').json()['people']
        self.assertEqual(next(p for p in people if p['id']==other['id'])['total_cents'],5000)
        self.assertEqual(next(p for p in people if p['id']==current['id'])['total_cents'],0)

    def test_corrections_reallocate_atomically_and_delete_updates_totals(self):
        category = self.category()
        ids = [p['id'] for p in self.participants()]
        payload = self.cost_payload(category['id'], ids)
        cost = self.save_cost(payload)
        changed = self.client.put(f"/api/expenses/costs/{cost['id']}", json={**payload,'amount':'12.01','participant_ids':[ids[0]]})
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(changed.json()['cost']['allocations'][0]['share_cents'],1201)
        invalid = self.client.put(f"/api/expenses/costs/{cost['id']}", json={**payload,'participant_ids':[876543]})
        self.assertEqual(invalid.status_code,422,invalid.text)
        self.assertEqual(self.client.get('/api/expenses/summary').json()['spent_cents'],1201)
        self.assertEqual(self.client.delete(f"/api/expenses/costs/{cost['id']}").status_code,200)
        self.assertEqual(self.client.get('/api/expenses/summary').json()['spent_cents'],0)

    def test_transfer_histories_idempotency_corrections_and_remaining_math(self):
        payload = {'kind':'origin','amount':'200','transfer_date':'2026-10-01','note':'sent','request_id':'origin'}
        origin = self.client.post('/api/expenses/transfers',json=payload)
        self.assertEqual(origin.status_code,200,origin.text)
        origin = origin.json()['transfer']
        self.assertEqual(self.client.post('/api/expenses/transfers',json=payload).json()['transfer']['id'],origin['id'])
        self.assertEqual(self.client.post('/api/expenses/transfers',json={**payload,'amount':'201'}).status_code,409)
        received = self.client.post('/api/expenses/transfers',json={**payload,'kind':'received','amount':'90','request_id':'received'}).json()['transfer']
        self.save_cost(self.cost_payload(self.category()['id'],[p['id'] for p in self.participants()]))
        summary = self.client.get('/api/expenses/summary').json()
        self.assertEqual(summary, {'origin_cents':20000,'received_cents':9000,'spent_cents':10000,'remaining_cents':-1000})
        updated = self.client.put(f"/api/expenses/transfers/{received['id']}",json={**payload,'kind':'received','amount':'150'})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(self.client.get('/api/expenses/summary').json()['remaining_cents'],5000)
        history = self.client.get('/api/expenses/transfers',params={'kind':'origin','page_size':1}).json()
        self.assertEqual(history['pagination']['total_items'],1)
        self.assertEqual(history['transfers'][0]['id'],origin['id'])
        self.assertEqual(self.client.delete(f"/api/expenses/transfers/{received['id']}").status_code,200)
        self.assertEqual(self.client.get('/api/expenses/summary').json()['received_cents'],0)

    def test_readonly_members_and_user_ownership_and_admin_category_management(self):
        category = self.category()
        ids = [p['id'] for p in self.participants()]
        admin_cost = self.save_cost(self.cost_payload(category['id'], ids))
        transfer_payload = {'kind':'received','amount':'20','transfer_date':'2026-10-01','request_id':'admin-transfer'}
        admin_transfer = self.client.post('/api/expenses/transfers',json=transfer_payload).json()['transfer']
        self.set_actor_role('user')
        own = self.save_cost(self.cost_payload(category['id'],ids,request_id='own'))
        self.assertEqual(self.client.put(f"/api/expenses/costs/{own['id']}",json=self.cost_payload(category['id'],ids,amount='30')).status_code,200)
        # Existing admin records created by this actor remain owned after changing role.
        with db_connection() as conn:
            conn.execute('UPDATE expense_costs SET created_by=? WHERE id=?',(self.other_user_id,admin_cost['id']))
            conn.execute('UPDATE expense_transfers SET created_by=? WHERE id=?',(self.other_user_id,admin_transfer['id']))
        self.assertEqual(self.client.delete(f"/api/expenses/costs/{admin_cost['id']}").status_code,403)
        self.assertEqual(self.client.put(f"/api/expenses/costs/{admin_cost['id']}",json=self.cost_payload(category['id'],ids)).status_code,403)
        self.assertEqual(self.client.delete(f"/api/expenses/transfers/{admin_transfer['id']}").status_code,403)
        self.assertEqual(self.client.put(f"/api/expenses/transfers/{admin_transfer['id']}",json=transfer_payload).status_code,403)
        self.assertEqual(self.client.patch(f"/api/expenses/categories/{category['id']}",json={'name':'No'}).status_code,403)
        self.category('User-created')
        self.set_actor_role('member')
        for route in ('participants','categories','summary','people','costs','transfers'):
            self.assertEqual(self.client.get('/api/expenses/'+route).status_code,200)
        self.assertEqual(self.client.post('/api/expenses/categories',json={'name':'No'}).status_code,403)
        self.assertEqual(self.client.post('/api/expenses/costs',json=self.cost_payload(category['id'],ids)).status_code,403)
        self.assertEqual(self.client.post('/api/expenses/transfers',json=transfer_payload).status_code,403)
        self.assertEqual(self.client.delete(f"/api/expenses/costs/{own['id']}").status_code,403)
        self.set_actor_role('admin')
        self.assertEqual(self.client.delete(f"/api/expenses/costs/{admin_cost['id']}").status_code,200)

    def test_participant_endpoint_is_minimal_and_pending_disabled_accounts_denied(self):
        pending = self.account('pending-person')
        with db_connection() as conn:
            conn.execute("UPDATE users SET status='pending' WHERE id=?",(pending['id'],))
        participants = self.participants()
        self.assertEqual(set(participants[0]),{'id','user_id','username','role','status','eligible'})
        self.assertFalse(next(p for p in participants if p['user_id']==pending['id'])['eligible'])
        self.set_actor_role('member')
        with db_connection() as conn:
            conn.execute("UPDATE users SET status='disabled' WHERE id=?",(self.actor_id,))
        self.assertEqual(self.client.get('/api/expenses/people').status_code,401)
        with TestClient(self.client.app) as anonymous:
            self.assertEqual(anonymous.get('/api/expenses/summary').status_code,401)

    def test_category_catalog_exposes_saved_historical_paths_for_search(self):
        parent = self.category('VPS')
        child = self.category('Hetzner',parent['id'])
        self.save_cost(self.cost_payload(child['id'],[p['id'] for p in self.participants()]))
        self.client.patch(f"/api/expenses/categories/{parent['id']}",json={'name':'Servers'})
        categories = self.client.get('/api/expenses/categories').json()['categories']
        current = next(c for c in categories if c['id']==child['id'])
        self.assertEqual(current['path'],'Servers / Hetzner')
        self.assertEqual(current['historical_paths'],['VPS / Hetzner'])
        self.assertEqual(next(c for c in categories if c['id']==parent['id'])['historical_paths'],[])

    def test_large_cent_totals_remain_exact_without_sqlite_sum_overflow(self):
        category = self.category()
        ids = [p['id'] for p in self.participants()]
        for index in range(2):
            self.save_cost(self.cost_payload(category['id'],ids,amount='92233720368547758.07',request_id=f'large-{index}'))
            transfer = self.client.post('/api/expenses/transfers',json={'kind':'received','amount':'92233720368547758.07',
                'transfer_date':'2026-10-01','request_id':f'large-transfer-{index}'})
            self.assertEqual(transfer.status_code,200,transfer.text)
        expected = 2*9223372036854775807
        self.assertEqual(self.client.get('/api/expenses/summary').json()['spent_cents'],expected)
        self.assertEqual(self.client.get('/api/expenses/summary').json()['remaining_cents'],0)
        self.assertEqual(self.client.get('/api/expenses/people').json()['total_cents'],expected)
        self.assertEqual(self.client.get('/api/expenses/costs').json()['filtered_total_cents'],expected)
        self.assertEqual(self.client.get('/api/expenses/costs',params={'participant_id':ids[0]}).json()['filtered_total_cents'],9223372036854775808)

    def test_one_cent_split_allows_zero_shares_and_shares_sum_to_amount(self):
        ids = [p['id'] for p in self.participants()]
        cost = self.save_cost(self.cost_payload(self.category()['id'],ids,amount='0.01'))
        self.assertEqual([a['share_cents'] for a in cost['allocations']],[1,0])
        self.assertEqual(sum(a['share_cents'] for a in cost['allocations']),1)

    def test_failed_allocation_database_insert_rolls_back_cost_and_all_shares(self):
        category = self.category()
        ids = [p['id'] for p in self.participants()]
        with db_connection() as conn:
            conn.execute(f"""CREATE TRIGGER fail_second_share BEFORE INSERT ON expense_allocations
                WHEN NEW.participant_id={ids[1]} BEGIN SELECT RAISE(ABORT,'allocation unavailable'); END""")
        with TestClient(self.client.app,raise_server_exceptions=False) as failed:
            failed.cookies.update(self.client.cookies)
            response = failed.post('/api/expenses/costs',json=self.cost_payload(category['id'],ids))
            self.assertEqual(response.status_code,500)
        with db_connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM expense_costs').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT count(*) FROM expense_allocations').fetchone()[0],0)

    def test_retained_historical_people_and_category_can_be_corrected_without_rewriting_purpose(self):
        category = self.category()
        ids = [p['id'] for p in self.participants()]
        payload = self.cost_payload(category['id'],ids)
        cost = self.save_cost(payload)
        self.client.patch(f"/api/expenses/categories/{category['id']}",json={'name':'Servers','archived':True})
        self.client.delete(f'/api/users/{self.other_user_id}')
        corrected = self.client.put(f"/api/expenses/costs/{cost['id']}",json={**payload,'expense_date':'2026-10-02'})
        self.assertEqual(corrected.status_code,200,corrected.text)
        self.assertEqual(corrected.json()['cost']['category_path'],'VPS')
        self.assertEqual(corrected.json()['cost']['allocations'],cost['allocations'])
        retry = self.client.post('/api/expenses/costs',json=payload)
        self.assertEqual(retry.status_code,200,retry.text)
        self.assertEqual(retry.json()['cost']['id'],cost['id'])

    def test_timezone_presets_use_inclusive_calendar_dates(self):
        self.category()
        fixed = datetime.fromisoformat('2026-10-13T01:00:00+00:00')
        with patch('backend.app.features.expenses.validation.datetime') as clock:
            clock.now.side_effect = lambda zone: fixed.astimezone(zone)
            self.client.patch('/api/preferences/timezone',json={'timezone':'America/New_York'})
            for period, days in (('day',1),('week',7),('month',30)):
                response = self.client.get('/api/expenses/people',params={'period':period})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()['end_date'],'2026-10-12')
                self.assertEqual(response.json()['start_date'],(fixed.date()-timedelta(days=days)).isoformat())


if __name__ == '__main__':
    unittest.main()
