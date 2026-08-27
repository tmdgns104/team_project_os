from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


def check(name: str, value: bool) -> None:
    print(f"[LIVE SIM] {name}: {'PASS' if value else 'FAIL'}")
    if not value:
        raise SystemExit(1)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ['PROJECT_OS_DB'] = str(Path(td) / 'live-sim.db')
        from app import main as app_main
        app_main.DB_PATH = Path(os.environ['PROJECT_OS_DB'])
        app_main.SEED_DEMO = False
        app_main.init_db()
        with TestClient(app_main.app) as client:
            draft = client.post('/api/design-drafts', json={'member_name':'sim-user','provider':'codex','name_hint':'AI Design Draft'}).json()
            check('draft_created', draft.get('lifecycle') == 'draft')

            turns = [
                {
                    'project_updates': {'name':'HMI MES Live Simulator','goal':'작은 컨베이어 생산라인의 상태와 실적을 HMI/MES에서 확인한다','project_type':'manufacturing_automation'},
                    'requirements': [{'ref':'REQ-001','title':'PLC 상태 수집','detail':'운전 상태를 수집한다','status':'defined'}],
                    'decisions': [{'title':'PLC 계열','body':'Mitsubishi PLC','status':'accepted'}],
                    'document_updates': [], 'design_updates': [], 'pending': []
                },
                {
                    'project_updates': {'name':'HMI MES Live Simulator','goal':'작은 컨베이어 생산라인의 상태와 실적을 HMI/MES에서 확인한다','project_type':'manufacturing_automation','scope':'시뮬레이터 우선 V1'},
                    'requirements': [
                        {'ref':'REQ-001','title':'PLC 상태 수집','detail':'운전 상태를 수집한다','status':'defined'},
                        {'ref':'REQ-002','title':'생산 실적 저장','detail':'생산/불량 수량을 저장한다','status':'defined'}],
                    'decisions': [
                        {'title':'PLC 계열','body':'Mitsubishi PLC','status':'accepted'},
                        {'title':'V1 DB','body':'SQLite를 AI 임시 결정으로 사용','status':'provisional'}],
                    'document_updates': [],
                    'design_updates': [{
                        'view':'process','mode':'replace',
                        'nodes':[{'key':'plc','label':'PLC 감지','kind':'step'},{'key':'collect','label':'데이터 수집','kind':'step'},{'key':'save','label':'실적 저장','kind':'step'}],
                        'edges':[{'source':'plc','target':'collect','label':'status'},{'source':'collect','target':'save','label':'record'}]
                    }],
                    'pending':['실제 PLC 통신 방식']
                }
            ]
            for idx, state in enumerate(turns, 1):
                result = client.put(f"/api/design-drafts/{draft['id']}/sync", json={'member_name':'sim-user','state':state})
                check(f'turn_{idx}_sync', result.status_code == 200)
                snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
                print(f"[LIVE SIM] turn={idx} docs_updated_by={next(d for d in snap['documents'] if d['doc_type']=='plan')['updated_by']} req={len(snap['requirements'])} decisions={len(snap['decisions'])} nodes={len(snap['nodes'])}")

            final_snap = client.get(f"/api/projects/{draft['id']}/snapshot").json()
            check('documents_live', 'SQLite' in next(d for d in final_snap['documents'] if d['doc_type']=='plan')['content'])
            check('requirements_live', len(final_snap['requirements']) == 2)
            check('provisional_visible', any(d['status']=='provisional' for d in final_snap['decisions']))
            check('process_canvas_live', len([n for n in final_snap['nodes'] if n['view']=='process']) == 3)

            promoted = client.post(f"/api/design-drafts/{draft['id']}/promote", json={'member_name':'sim-user','state':turns[-1]}).json()['project']
            check('promoted_to_active', promoted.get('lifecycle') == 'active')
            print(f"[LIVE SIM] PROJECT PROMOTED: ID={promoted['id']} name={promoted['name']}")
            print('[LIVE SIM] LIVE DESIGN DRAFT E2E: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
