from __future__ import annotations

import re
from urllib.parse import urljoin

from tests.support import AuthenticatedWorkspaceTestCase


class UpdateAssetTests(AuthenticatedWorkspaceTestCase):
    def test_html_and_styles_use_a_new_asset_namespace(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        paths = re.findall(r'(?:src|href)="(/static/[^\"]+)"', response.text)
        self.assertTrue(paths)
        self.assertTrue(all(path.startswith('/static/v1.3.1/') for path in paths), paths)
        self.assertIn('/static/v1.3.1/js/app.js', paths)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_complete_module_graph_resolves_under_versioned_namespace(self):
        pending = ['/static/v1.3.1/js/app.js']
        visited = set()
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            for target in re.findall(r'(?:from\s*|import\s*\(\s*)[\"\']([^\"\']+\.js)[\"\']', response.text):
                imported = urljoin(path, target)
                self.assertTrue(imported.startswith('/static/v1.3.1/js/'), imported)
                pending.append(imported)
        self.assertGreater(len(visited), 30)
        self.assertIn('/static/v1.3.1/js/app/pageRegistry.js', visited)
        self.assertIn('/static/v1.3.1/js/features/overview/page.js', visited)
        self.assertIn('/static/v1.3.1/js/features/used/page.js', visited)

    def test_html_static_and_authenticated_api_responses_do_not_reuse_cache(self):
        for path in ['/', '/static/js/app/pageRegistry.js', '/static/v1.3.1/js/app.js', '/api/auth/me', '/openapi.json']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn('no-store', response.headers.get('cache-control', ''), path)
            self.assertEqual(response.headers.get('x-bd-app-version'), '1.3.1', path)
        response = self.client.get('/static/v1.3.1/js/app.js')
        conditional = self.client.get('/static/v1.3.1/js/app.js', headers={'if-none-match': response.headers['etag']})
        self.assertIn('no-store', conditional.headers.get('cache-control', ''))

    def test_runtime_version_and_all_roles_have_the_new_navigation_permission(self):
        self.assertEqual(self.client.get('/api/health').json(), {'status': 'ok', 'version': '1.3.1'})
        self.assertEqual(self.client.get('/openapi.json').json()['info']['version'], '1.3.1')
        for role in ['admin', 'member', 'user']:
            self.set_actor_role(role)
            response = self.client.get('/api/auth/me')
            self.assertEqual(response.status_code, 200)
            self.assertIn('expenses:read', response.json()['user']['capabilities'])
