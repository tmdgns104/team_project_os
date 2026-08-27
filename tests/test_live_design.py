from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from local_bridge.project_cli import blank_live_state, extract_live_delta, merge_live_state, promote_live_draft, sync_live_draft


class LiveDeltaTests(unittest.TestCase):
    def test_extract_live_delta_hides_machine_block(self):
        raw = '좋습니다. SQLite로 임시 진행하겠습니다.\n<PROJECT_OS_DELTA>{"decisions":[{"title":"DB","body":"SQLite","status":"provisional"}]}</PROJECT_OS_DELTA>'
        answer, delta = extract_live_delta(raw)
        self.assertEqual(answer, '좋습니다. SQLite로 임시 진행하겠습니다.')
        self.assertEqual(delta['decisions'][0]['status'], 'provisional')

    def test_merge_live_state_is_incremental_and_idempotent(self):
        state = blank_live_state()
        state = merge_live_state(state, {
            'project_updates': {'name': 'HMI MES'},
            'requirements': [{'ref':'REQ-001','title':'수집','detail':'PLC','status':'defined'}],
            'decisions': [{'title':'DB','body':'SQLite','status':'provisional'}],
        })
        state = merge_live_state(state, {
            'project_updates': {'goal': '실시간 생산 현황 표시'},
            'requirements': [{'ref':'REQ-001','title':'PLC 데이터 수집','detail':'운전/수량','status':'defined'}],
            'decisions': [{'title':'DB','body':'SQLite for V1','status':'provisional'}],
        })
        self.assertEqual(state['project_updates']['name'], 'HMI MES')
        self.assertEqual(state['project_updates']['goal'], '실시간 생산 현황 표시')
        self.assertEqual(len(state['requirements']), 1)
        self.assertEqual(state['requirements'][0]['title'], 'PLC 데이터 수집')
        self.assertEqual(len(state['decisions']), 1)
        self.assertIn('V1', state['decisions'][0]['body'])


class LiveDraftApiTests(unittest.TestCase):
    def test_live_draft_sync_updates_web_state_then_promotes(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ['PROJECT_OS_DB'] = os.path.join(td, 'live.db')
            from app import main as app_main
            app_main.DB_PATH = app_main.Path(os.environ['PROJECT_OS_DB'])
            app_main.SEED_DEMO = False
            app_main.init_db()
            with TestClient(app_main.app) as client:
                draft = client.post('/api/design-drafts', json={'member_name':'tester','provider':'codex','name_hint':'AI Design Draft'}).json()
                self.assertEqual(draft['lifecycle'], 'draft')

                state = {
                    'project_updates': {'name':'HMI MES Live','goal':'PLC 생산 데이터를 HMI/MES에서 실시간 표시','project_type':'manufacturing_automation'},
                    'requirements': [{'ref':'REQ-001','title':'PLC 데이터 수집','detail':'운전/수량/불량','status':'defined'}],
                    'decisions': [{'title':'V1 DB','body':'SQLite를 임시 사용','status':'provisional'}],
                    'document_updates': [],
                    'design_updates': [{
                        'view':'architecture','mode':'replace','nodes':[
                            {'key':'plc','label':'Mitsubishi PLC','kind':'device','detail':'user confirmed'},
                            {'key':'api','label':'FastAPI Gateway','kind':'service','detail':'AI provisional'},
                            {'key':'db','label':'SQLite','kind':'store','detail':'AI provisional'}],
                        'edges':[{'source':'plc','target':'api','label':'PLC Data'},{'source':'api','target':'db','label':'Record'}]
                    }],
                    'pending':['실제 PLC 통신 방식'],
                }
                r = client.put(f"/api/design-drafts/{draft['id']}/sync", json={'member_name':'tester','state':state})
                self.assertEqual(r.status_code, 200)
                snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                self.assertEqual(snap['project']['lifecycle'], 'draft')
                self.assertEqual(snap['project']['name'], 'HMI MES Live')
                self.assertEqual(len(snap['requirements']), 1)
                self.assertEqual(len(snap['decisions']), 1)
                self.assertEqual(snap['decisions'][0]['status'], 'provisional')
                self.assertEqual(len([n for n in snap['nodes'] if n['view']=='architecture']), 3)
                proposal = next(d for d in snap['documents'] if d['doc_type']=='proposal')
                self.assertIn('PLC 생산 데이터를', proposal['content'])
                plan = next(d for d in snap['documents'] if d['doc_type']=='plan')
                self.assertIn('SQLite', plan['content'])

                state['requirements'].append({'ref':'REQ-002','title':'생산 실적 조회','detail':'시간별 조회','status':'defined'})
                state['decisions'].append({'title':'PLC 계열','body':'Mitsubishi 사용','status':'accepted'})
                client.put(f"/api/design-drafts/{draft['id']}/sync", json={'member_name':'tester','state':state})
                snap2 = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                self.assertEqual(len(snap2['requirements']), 2)
                self.assertEqual(len(snap2['decisions']), 2)

                promoted = client.post(f"/api/design-drafts/{draft['id']}/promote", json={'member_name':'tester','state':state}).json()['project']
                self.assertEqual(promoted['lifecycle'], 'active')
                final = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                self.assertEqual(final['project']['lifecycle'], 'active')
                self.assertEqual(final['project']['name'], 'HMI MES Live')


if __name__ == '__main__':
    unittest.main()
