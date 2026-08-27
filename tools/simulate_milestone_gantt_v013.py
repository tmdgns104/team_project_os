from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


def check(name: str, ok: bool) -> None:
    print(f"[V013 GANTT] {name}: {'PASS' if ok else 'FAIL'}")
    if not ok:
        raise SystemExit(1)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["PROJECT_OS_DB"] = str(Path(td) / "v013.db")
        from app import main as app_main
        app_main.DB_PATH = Path(os.environ["PROJECT_OS_DB"])
        app_main.SEED_DEMO = False
        app_main.init_db()
        with TestClient(app_main.app) as client:
            draft = client.post('/api/design-drafts', json={
                'member_name':'sim-user','provider':'codex','name_hint':'HMI MES Gantt Simulation'
            }).json()
            check('draft_created', draft.get('lifecycle') == 'draft')
            state = {
                'project_updates': {
                    'name':'HMI MES Gantt Simulation',
                    'goal':'PLC 생산 상태와 실적을 수집하고 HMI에서 확인한다.',
                    'project_type':'manufacturing_automation',
                    'problem':'수작업 확인과 기록의 누락을 줄인다.',
                    'users':'작업자, 설비 담당자, 품질 담당자',
                    'deliverables':'PLC Gateway, Backend, HMI, DB, QA 문서',
                    'success_criteria':'Simulator E2E PASS 및 핵심 요구사항 검증',
                    'scope':'포함=Simulator/Backend/HMI/DB, 제외=실제 장비 구매',
                    'constraints':'Simulator-first, Windows Local',
                    'schedule':'상대 주차 기준으로 정의/설계→구현→통합/검증→인수 순서',
                    'team':'PM, 개발, QA',
                    'risks':'실제 PLC 프로토콜은 추후 확인',
                },
                'requirements':[{'ref':'REQ-001','title':'PLC 상태 수집','detail':'운전/알람 상태 수집','status':'defined'}],
                'decisions':[{'title':'PLC 계열','body':'Mitsubishi PLC','status':'accepted'}],
                'document_updates':[], 'design_updates':[], 'pending':['실제 시작일']
            }
            sync=client.put(f"/api/design-drafts/{draft['id']}/sync",json={'member_name':'sim-user','state':state})
            check('live_sync', sync.status_code == 200)
            snap=client.get(f"/api/projects/{draft['id']}/snapshot").json()
            check('documents_13', len(snap['documents']) == 13)
            milestone=next(d for d in snap['documents'] if d['doc_type']=='milestone')
            content=milestone['content']
            check('gantt_source_table', all(x in content for x in ['Phase','Task','Start Week','End Week','Owner','Status']))
            check('gantt_task_density', content.count('| MS-') >= 15)
            check('four_delivery_phases', all(x in content for x in ['A. 정의 및 설계','B. 구현','C. 통합 및 검증','D. 완료']))
            check('relative_schedule_warning', '상대 주차' in content)
            promoted=client.post(f"/api/design-drafts/{draft['id']}/promote",json={'member_name':'sim-user','state':state}).json()['project']
            check('promoted_active', promoted.get('lifecycle') == 'active')
            final=client.get(f"/api/projects/{draft['id']}/snapshot").json()
            final_milestone=next(d for d in final['documents'] if d['doc_type']=='milestone')['content']
            check('gantt_persists_after_apply', 'Start Week' in final_milestone and final_milestone.count('| MS-') >= 15)
            health=client.get('/api/health').json()
            check('health_version_013', health.get('version') == '0.13.0')
            print('[V013 GANTT] PROJECT + 13 DOCUMENTS + GANTT MILESTONE: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
